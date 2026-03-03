"""
Dropbox OAuth Service — Month 2

Same security philosophy as Google Drive:
- Metadata + hashes only — no file downloads
- Dropbox provides content_hash (SHA-256 based) natively
- OAuth PKCE flow with offline access for background refresh

Flow:
1. GET /api/v1/connections/dropbox/authorize → Dropbox OAuth URL
2. GET /api/v1/connections/dropbox/callback  → token exchange + index
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
import hashlib

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token
from app.models.file import StorageConnection, FileRecord

DROPBOX_AUTH_URL = "https://www.dropbox.com/oauth2/authorize"
DROPBOX_TOKEN_URL = "https://api.dropbox.com/oauth2/token"
DROPBOX_LIST_FOLDER_URL = "https://api.dropboxapi.com/2/files/list_folder"
DROPBOX_LIST_CONTINUE_URL = "https://api.dropboxapi.com/2/files/list_folder/continue"
DROPBOX_ACCOUNT_URL = "https://api.dropboxapi.com/2/users/get_current_account"
DROPBOX_SPACE_URL = "https://api.dropboxapi.com/2/users/get_space_usage"


def get_dropbox_auth_url(state: str) -> str:
    if not settings.DROPBOX_APP_KEY:
        raise ValueError("DROPBOX_APP_KEY not configured")

    callback = f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/connections/dropbox/callback"
    return (
        f"{DROPBOX_AUTH_URL}"
        f"?client_id={settings.DROPBOX_APP_KEY}"
        f"&redirect_uri={callback}"
        f"&response_type=code"
        f"&token_access_type=offline"
        f"&state={state}"
    )


async def exchange_dropbox_code(code: str) -> dict:
    callback = f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/connections/dropbox/callback"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            DROPBOX_TOKEN_URL,
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback,
            },
            auth=(settings.DROPBOX_APP_KEY, settings.DROPBOX_APP_SECRET),
        )
        resp.raise_for_status()
        return resp.json()


async def get_dropbox_account_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            DROPBOX_ACCOUNT_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=None,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("email", "unknown@dropbox.com")


async def refresh_dropbox_token(refresh_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            DROPBOX_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            auth=(settings.DROPBOX_APP_KEY, settings.DROPBOX_APP_SECRET),
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def index_dropbox(
    db: AsyncSession,
    connection: StorageConnection,
) -> dict:
    """
    Recursively list all files in Dropbox using list_folder.
    Dropbox content_hash is used as our hash (SHA-256 blocks — very accurate).
    """
    access_token = decrypt_token(connection.oauth_token_enc)

    # Get space usage
    try:
        async with httpx.AsyncClient() as client:
            space_resp = await client.post(
                DROPBOX_SPACE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if space_resp.status_code == 200:
                space = space_resp.json()
                connection.used_bytes = space.get("used", 0)
                alloc = space.get("allocation", {})
                connection.total_bytes = alloc.get("allocated", 0)
    except Exception:
        pass

    indexed = 0
    updated = 0
    total_bytes = 0

    # List folder recursively from root
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            DROPBOX_LIST_FOLDER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "path": "",
                "recursive": True,
                "include_media_info": False,
                "include_deleted": False,
                "include_has_explicit_shared_members": False,
                "limit": 2000,
            },
        )

        if resp.status_code == 401 and connection.refresh_token_enc:
            access_token = await refresh_dropbox_token(
                decrypt_token(connection.refresh_token_enc)
            )
            connection.oauth_token_enc = encrypt_token(access_token)
            resp = await client.post(
                DROPBOX_LIST_FOLDER_URL,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"path": "", "recursive": True, "include_media_info": False, "include_deleted": False, "limit": 2000},
            )

        resp.raise_for_status()
        data = resp.json()

    while True:
        for entry in data.get("entries", []):
            if entry[".tag"] != "file":
                continue

            size = entry.get("size", 0)
            total_bytes += size
            content_hash = entry.get("content_hash")
            remote_id = entry.get("id", entry["path_lower"])

            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.user_id == connection.user_id,
                    FileRecord.connection_id == connection.id,
                    FileRecord.remote_id == remote_id,
                )
            )
            existing = result.scalar_one_or_none()

            modified = _parse_dropbox_dt(entry.get("client_modified") or entry.get("server_modified"))

            if existing:
                existing.file_size = size
                existing.md5_hash = content_hash  # Dropbox content_hash stored as md5_hash for dedup
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
                    file_path=entry.get("path_display", entry["path_lower"]),
                    file_name=entry["name"],
                    file_size=size,
                    mime_type=_guess_mime(entry["name"]),
                    md5_hash=content_hash,
                    last_modified=modified,
                )
                db.add(record)
                indexed += 1

        if not data.get("has_more"):
            break

        async with httpx.AsyncClient(timeout=60) as client:
            cont_resp = await client.post(
                DROPBOX_LIST_CONTINUE_URL,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"cursor": data["cursor"]},
            )
            cont_resp.raise_for_status()
            data = cont_resp.json()

        await db.flush()

    connection.last_synced = datetime.now(timezone.utc)
    await db.flush()

    return {"files_indexed": indexed, "files_updated": updated, "total_bytes": total_bytes}


def _parse_dropbox_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _guess_mime(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif", "webp": "image/webp", "heic": "image/heic",
        "pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "mp4": "video/mp4", "mov": "video/quicktime", "avi": "video/avi",
        "mp3": "audio/mpeg", "zip": "application/zip", "tar": "application/x-tar",
    }
    return mime_map.get(ext, "application/octet-stream")
