"""
Google Drive OAuth Service — Month 2

Security philosophy:
- We NEVER download file contents — only metadata + MD5 hashes (provided by Drive API)
- OAuth tokens are encrypted at rest via Fernet before DB storage
- We request minimal scopes: drive.metadata.readonly + drive.readonly (for thumbnails only)
- Token refresh is handled transparently

Flow:
1. GET /api/v1/connections/google/authorize  → returns Google OAuth URL
2. User authenticates at Google
3. GET /api/v1/connections/google/callback   → exchanges code, stores encrypted tokens, starts index job
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token
from app.models.file import StorageConnection, FileRecord

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

# Minimal scopes — metadata + readonly for thumbnails
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


def get_google_auth_url(state: str) -> str:
    """Build Google OAuth authorization URL."""
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID not configured")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/connections/google/callback",
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_google_code(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/connections/google/callback",
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_google_user_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("email", "unknown@google.com")


async def refresh_google_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def index_google_drive(
    db: AsyncSession,
    connection: StorageConnection,
    page_size: int = 1000,
) -> dict:
    """
    Index all files in Google Drive using metadata only.
    Uses Drive API's built-in MD5 checksums — no download required.

    Returns: { files_indexed, files_updated, total_bytes }
    """
    access_token = decrypt_token(connection.oauth_token_enc)

    # Try to get quota info
    try:
        async with httpx.AsyncClient() as client:
            about_resp = await client.get(
                "https://www.googleapis.com/drive/v3/about",
                params={"fields": "storageQuota"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if about_resp.status_code == 200:
                quota = about_resp.json().get("storageQuota", {})
                connection.total_bytes = int(quota.get("limit", 0))
                connection.used_bytes = int(quota.get("usage", 0))
    except Exception:
        pass

    indexed = 0
    updated = 0
    total_bytes = 0
    page_token: Optional[str] = None

    fields = (
        "nextPageToken,"
        "files(id,name,mimeType,size,md5Checksum,modifiedTime,createdTime,"
        "parents,trashed,thumbnailLink)"
    )

    while True:
        params: dict = {
            "pageSize": page_size,
            "fields": fields,
            "q": "trashed=false",  # skip trash
            "orderBy": "modifiedTime desc",
        }
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                GOOGLE_DRIVE_FILES_URL,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            # Handle expired token
            if resp.status_code == 401 and connection.refresh_token_enc:
                refresh_data = await refresh_google_token(
                    decrypt_token(connection.refresh_token_enc)
                )
                new_access = refresh_data["access_token"]
                connection.oauth_token_enc = encrypt_token(new_access)
                access_token = new_access
                # Retry
                resp = await client.get(
                    GOOGLE_DRIVE_FILES_URL,
                    params=params,
                    headers={"Authorization": f"Bearer {new_access}"},
                )

            resp.raise_for_status()
            data = resp.json()

        for gfile in data.get("files", []):
            # Skip folders and Google Docs (no binary size)
            if gfile.get("mimeType", "").startswith("application/vnd.google-apps"):
                continue

            size = int(gfile.get("size", 0))
            total_bytes += size

            # Upsert by remote_id
            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.user_id == connection.user_id,
                    FileRecord.connection_id == connection.id,
                    FileRecord.remote_id == gfile["id"],
                )
            )
            existing = result.scalar_one_or_none()

            parents = gfile.get("parents", [])
            path = f"/drive/{'/'.join(parents)}/{gfile['name']}"

            if existing:
                existing.file_size = size
                existing.md5_hash = gfile.get("md5Checksum")
                existing.last_modified = _parse_dt(gfile.get("modifiedTime"))
                existing.thumbnail_key = gfile.get("thumbnailLink")
                existing.is_deleted = False
                existing.indexed_at = datetime.now(timezone.utc)
                updated += 1
            else:
                record = FileRecord(
                    id=str(uuid.uuid4()),
                    user_id=connection.user_id,
                    connection_id=connection.id,
                    remote_id=gfile["id"],
                    file_path=path,
                    file_name=gfile["name"],
                    file_size=size,
                    mime_type=gfile.get("mimeType"),
                    md5_hash=gfile.get("md5Checksum"),
                    last_modified=_parse_dt(gfile.get("modifiedTime")),
                    created_date=_parse_dt(gfile.get("createdTime")),
                    # Store Drive thumbnail URL directly (no download needed)
                    thumbnail_key=gfile.get("thumbnailLink"),
                )
                db.add(record)
                indexed += 1

        page_token = data.get("nextPageToken")
        if not page_token:
            break

        await db.flush()  # Flush each page to avoid huge transactions

    connection.last_synced = datetime.now(timezone.utc)
    await db.flush()

    return {
        "files_indexed": indexed,
        "files_updated": updated,
        "total_bytes": total_bytes,
    }


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
