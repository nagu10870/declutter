"""
OneDrive OAuth Service — Month 3

Uses Microsoft Graph API (MSAL) for OneDrive access.
Follows same privacy model: metadata + SHA1 hashes only — no file downloads.

Flow:
1. GET /api/v1/connections/onedrive/authorize → Microsoft OAuth URL
2. GET /api/v1/connections/onedrive/callback  → token exchange + background index
"""

from datetime import datetime, timezone
from typing import Optional
import uuid
import httpx

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token
from app.models.file import StorageConnection, FileRecord

MS_AUTH_BASE = "https://login.microsoftonline.com"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = ["Files.Read", "User.Read", "offline_access"]


def get_onedrive_auth_url(state: str) -> str:
    if not settings.ONEDRIVE_CLIENT_ID:
        raise ValueError("ONEDRIVE_CLIENT_ID not configured")
    callback = _callback_url()
    scope_str = "%20".join(SCOPES)
    return (
        f"{MS_AUTH_BASE}/{settings.ONEDRIVE_TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={settings.ONEDRIVE_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={callback}"
        f"&scope={scope_str}"
        f"&state={state}"
        f"&response_mode=query"
    )


async def exchange_onedrive_code(code: str) -> dict:
    callback = _callback_url()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MS_AUTH_BASE}/{settings.ONEDRIVE_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": settings.ONEDRIVE_CLIENT_ID,
                "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": callback,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_onedrive_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MS_AUTH_BASE}/{settings.ONEDRIVE_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": settings.ONEDRIVE_CLIENT_ID,
                "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_onedrive_user_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("mail") or data.get("userPrincipalName", "unknown@microsoft.com")


async def index_onedrive(
    db: AsyncSession,
    connection: StorageConnection,
) -> dict:
    """
    Index all OneDrive files using Microsoft Graph delta queries.
    Graph provides SHA1 hash natively — no downloads needed.
    """
    access_token = decrypt_token(connection.oauth_token_enc)

    # Get storage quota
    try:
        async with httpx.AsyncClient() as client:
            drive_resp = await client.get(
                f"{GRAPH_BASE}/me/drive",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if drive_resp.status_code == 200:
                drive_data = drive_resp.json()
                quota = drive_data.get("quota", {})
                connection.total_bytes = quota.get("total", 0)
                connection.used_bytes = quota.get("used", 0)
    except Exception:
        pass

    indexed = 0
    updated = 0
    total_bytes = 0

    # List all files recursively using /me/drive/root/delta
    next_url: Optional[str] = f"{GRAPH_BASE}/me/drive/root/delta?$select=id,name,size,file,parentReference,lastModifiedDateTime,createdDateTime,deleted"

    while next_url:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                next_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            # Handle token expiry
            if resp.status_code == 401 and connection.refresh_token_enc:
                token_data = await refresh_onedrive_token(
                    decrypt_token(connection.refresh_token_enc)
                )
                access_token = token_data["access_token"]
                connection.oauth_token_enc = encrypt_token(access_token)
                if "refresh_token" in token_data:
                    connection.refresh_token_enc = encrypt_token(token_data["refresh_token"])
                resp = await client.get(
                    next_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

            resp.raise_for_status()
            data = resp.json()

        for item in data.get("value", []):
            # Skip folders
            if "file" not in item:
                continue
            # Skip deleted items
            if item.get("deleted"):
                continue

            size = item.get("size", 0)
            total_bytes += size
            remote_id = item["id"]
            file_hash = item.get("file", {}).get("hashes", {}).get("sha1Hash")
            parent_path = item.get("parentReference", {}).get("path", "/drive/root:")
            parent_path = parent_path.replace("/drive/root:", "")
            file_path = f"{parent_path}/{item['name']}"

            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.user_id == connection.user_id,
                    FileRecord.connection_id == connection.id,
                    FileRecord.remote_id == remote_id,
                )
            )
            existing = result.scalar_one_or_none()

            modified = _parse_dt(item.get("lastModifiedDateTime"))
            created = _parse_dt(item.get("createdDateTime"))

            if existing:
                existing.file_size = size
                existing.md5_hash = file_hash  # SHA1 stored in md5_hash field for dedup
                existing.last_modified = modified
                existing.is_deleted = False
                existing.indexed_at = datetime.now(timezone.utc)
                updated += 1
            else:
                record = FileRecord(
                    id=str(uuid.uuid4()),
                    user_id=connection.user_id,
                    connection_id=connection.id,
                    remote_id=remote_id,
                    file_path=file_path,
                    file_name=item["name"],
                    file_size=size,
                    mime_type=item.get("file", {}).get("mimeType"),
                    md5_hash=file_hash,
                    last_modified=modified,
                    created_date=created,
                )
                db.add(record)
                indexed += 1

        # Handle pagination
        next_url = data.get("@odata.nextLink") or data.get("@odata.deltaLink")
        if "@odata.deltaLink" in data:
            # Store delta link for incremental syncs (Month 4 optimization)
            break

        await db.flush()

    connection.last_synced = datetime.now(timezone.utc)
    await db.flush()

    return {"files_indexed": indexed, "files_updated": updated, "total_bytes": total_bytes}


def _callback_url() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/connections/onedrive/callback"


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
