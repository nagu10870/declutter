"""
Share Links Service — Month 4

Allows Pro users to generate read-only share links for:
  - Duplicate report snapshots (share with team/client)
  - Suggestion lists
  - File index exports

Security:
  - JWT-signed tokens with expiry (default: 7 days)
  - No auth required to view a shared link (read-only)
  - User can revoke a link at any time
  - Links reveal only file names/sizes, never paths or hashes

Share tokens are stored in share_links table for audit + revocation.
"""

import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError

from app.core.config import settings
from app.models.extended import ShareLink


def generate_share_token(
    user_id: str,
    link_type: str,  # "duplicates" | "suggestions" | "index"
    expires_days: int = 7,
) -> str:
    """Generate a signed JWT share token."""
    payload = {
        "sub": user_id,
        "type": "share",
        "link_type": link_type,
        "jti": secrets.token_urlsafe(16),
        "exp": datetime.now(timezone.utc) + timedelta(days=expires_days),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_share_token(token: str) -> Optional[dict]:
    """Decode and validate a share token. Returns payload or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "share":
            return None
        return payload
    except JWTError:
        return None


async def create_share_link(
    db: AsyncSession,
    user_id: str,
    link_type: str,
    label: Optional[str] = None,
    expires_days: int = 7,
) -> "ShareLink":
    """Create a new share link and persist it."""
    token = generate_share_token(user_id, link_type, expires_days)
    slug = secrets.token_urlsafe(10)

    link = ShareLink(
        id=str(uuid.uuid4()),
        user_id=user_id,
        slug=slug,
        link_type=link_type,
        token=token,
        label=label or f"Shared {link_type}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
    )
    db.add(link)
    await db.flush()
    return link


async def get_share_link(db: AsyncSession, slug: str) -> Optional["ShareLink"]:
    """Look up a share link by its slug."""
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.slug == slug,
            ShareLink.revoked == False,
            ShareLink.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_share_link(db: AsyncSession, link_id: str, user_id: str) -> bool:
    result = await db.execute(
        select(ShareLink).where(ShareLink.id == link_id, ShareLink.user_id == user_id)
    )
    link = result.scalar_one_or_none()
    if link:
        link.revoked = True
        await db.flush()
        return True
    return False
