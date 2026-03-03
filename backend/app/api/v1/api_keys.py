"""
API Key Management — Month 5

Allows Pro users to generate API keys for programmatic access.

POST   /api/v1/api-keys           → Create new API key (returns raw key ONCE)
GET    /api/v1/api-keys           → List existing keys (never returns raw key)
DELETE /api/v1/api-keys/{id}      → Revoke a key

Security:
  - Raw key is returned ONLY on creation and never stored
  - We store SHA256(key) for verification
  - Key format: dcl_{random_32_chars} (urlsafe base64)
  - Each key has optional scopes: read, write, delete, admin
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.extended import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

VALID_SCOPES = {"read", "write", "delete", "admin"}


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["read"]
    expires_days: Optional[int] = None


@router.post("")
async def create_api_key(
    req: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="API keys require Pro plan")

    # Validate scopes
    invalid = set(req.scopes) - VALID_SCOPES
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid scopes: {invalid}")

    # Check limit: max 10 active keys per user
    existing = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id, ApiKey.revoked == False)
    )
    if len(existing.scalars().all()) >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 API keys per account")

    # Generate key
    raw_key = f"dcl_{secrets.token_urlsafe(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    expires_at = None
    if req.expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_days)

    key = ApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=req.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=",".join(req.scopes),
        expires_at=expires_at,
    )
    db.add(key)
    await db.commit()

    # !! Raw key returned ONLY HERE — never again
    return {
        "id": key.id,
        "name": key.name,
        "key": raw_key,  # ← ONLY time this is returned
        "prefix": key_prefix,
        "scopes": req.scopes,
        "expires_at": expires_at,
        "created_at": key.created_at,
        "warning": "Save this key now — it will not be shown again.",
    }


@router.get("")
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id, ApiKey.revoked == False)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "prefix": k.key_prefix,
            "scopes": k.scopes.split(","),
            "last_used_at": k.last_used_at,
            "expires_at": k.expires_at,
            "created_at": k.created_at,
        }
        for k in keys
    ]


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.revoked = True
    await db.commit()
    return {"revoked": True, "key_id": key_id}


async def get_user_from_api_key(raw_key: str, db: AsyncSession) -> Optional[User]:
    """Authenticate via API key. Updates last_used tracking."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey, User)
        .join(User, User.id == ApiKey.user_id)
        .where(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked == False,
        )
    )
    row = result.one_or_none()
    if not row:
        return None
    api_key, user = row

    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    # Update last used
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()
    return user
