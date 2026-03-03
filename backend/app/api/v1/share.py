"""
Share Links Routes — Month 4

POST /api/v1/share              → Create a share link
GET  /api/v1/share              → List my share links
DELETE /api/v1/share/{id}       → Revoke a share link
GET  /api/v1/share/view/{slug}  → View shared content (no auth required)
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.extended import ShareLink
from app.services.share.share_service import (
    create_share_link, get_share_link, revoke_share_link, verify_share_token
)

router = APIRouter(prefix="/share", tags=["share"])


class CreateShareLinkRequest(BaseModel):
    link_type: str = "duplicates"  # "duplicates" | "suggestions" | "index"
    label: Optional[str] = None
    expires_days: int = 7


@router.post("")
async def create_link(
    req: CreateShareLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.link_type not in ("duplicates", "suggestions", "index"):
        raise HTTPException(status_code=400, detail="Invalid link_type")
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Share links require Pro plan")

    link = await create_share_link(
        db, current_user.id, req.link_type,
        label=req.label, expires_days=req.expires_days
    )
    await db.commit()

    return {
        "id": link.id,
        "slug": link.slug,
        "link_type": link.link_type,
        "label": link.label,
        "url": f"{_base_url()}/share/{link.slug}",
        "expires_at": link.expires_at,
    }


@router.get("")
async def list_links(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.user_id == current_user.id,
            ShareLink.revoked == False,
        ).order_by(ShareLink.created_at.desc())
    )
    links = result.scalars().all()
    return [
        {
            "id": l.id,
            "slug": l.slug,
            "link_type": l.link_type,
            "label": l.label,
            "views": l.views,
            "url": f"{_base_url()}/share/{l.slug}",
            "expires_at": l.expires_at,
            "created_at": l.created_at,
        }
        for l in links
    ]


@router.delete("/{link_id}")
async def revoke_link(
    link_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    success = await revoke_share_link(db, link_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Share link not found")
    await db.commit()
    return {"revoked": True}


@router.get("/view/{slug}")
async def view_shared(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """View shared content — no authentication required."""
    link = await get_share_link(db, slug)
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    # Verify token
    payload = verify_share_token(link.token)
    if not payload:
        raise HTTPException(status_code=410, detail="Share link has expired")

    # Increment view count
    link.views += 1
    await db.flush()

    user_id = payload["sub"]
    link_type = payload["link_type"]

    if link_type == "duplicates":
        from app.models.file import DuplicateGroup, FileRecord
        from sqlalchemy import text
        result = await db.execute(
            select(DuplicateGroup).where(
                DuplicateGroup.user_id == user_id,
                DuplicateGroup.resolved == False,
            ).limit(50)
        )
        groups = result.scalars().all()
        return {
            "link_type": "duplicates",
            "label": link.label,
            "groups": [
                {"id": g.id, "match_type": g.match_type, "total_wasted_bytes": g.total_wasted_bytes}
                for g in groups
            ],
        }

    elif link_type == "suggestions":
        from app.models.file import Suggestion
        result = await db.execute(
            select(Suggestion).where(
                Suggestion.user_id == user_id,
                Suggestion.dismissed == False,
                Suggestion.applied == False,
            ).limit(20)
        )
        suggestions = result.scalars().all()
        return {
            "link_type": "suggestions",
            "label": link.label,
            "suggestions": [
                {"title": s.title, "bytes_savings": s.bytes_savings, "risk_level": s.risk_level}
                for s in suggestions
            ],
        }

    raise HTTPException(status_code=400, detail="Unknown link type")


def _base_url():
    from app.core.config import settings
    return settings.FRONTEND_URL
