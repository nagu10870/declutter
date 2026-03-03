"""
Suggestions Routes — Month 3

GET    /api/v1/suggestions              → List active suggestions (sorted by priority)
POST   /api/v1/suggestions/generate     → Re-run rules engine, refresh suggestions
POST   /api/v1/suggestions/{id}/apply   → Apply suggestion (soft-delete files)
POST   /api/v1/suggestions/{id}/dismiss → Dismiss suggestion (won't show again)
GET    /api/v1/suggestions/stats        → Total potential savings across all suggestions
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import Suggestion
from app.services.ai.suggestions_engine import generate_suggestions, apply_suggestion
from datetime import datetime, timezone

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.get("")
async def list_suggestions(
    include_dismissed: bool = Query(default=False),
    include_applied: bool = Query(default=False),
    risk_level: str | None = Query(default=None, description="Filter: low, medium, high"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return active cleanup suggestions sorted by priority (low risk + biggest savings first)."""
    q = select(Suggestion).where(Suggestion.user_id == current_user.id)

    if not include_dismissed:
        q = q.where(Suggestion.dismissed == False)
    if not include_applied:
        q = q.where(Suggestion.applied == False)
    if risk_level:
        q = q.where(Suggestion.risk_level == risk_level)

    q = q.order_by(
        # Low risk first
        func.case(
            (Suggestion.risk_level == "low", 0),
            (Suggestion.risk_level == "medium", 1),
            else_=2,
        ),
        Suggestion.bytes_savings.desc(),
    )

    result = await db.execute(q)
    suggestions = result.scalars().all()

    return [_serialize(s) for s in suggestions]


@router.get("/stats")
async def suggestions_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick summary of all pending suggestions."""
    result = await db.execute(
        select(
            func.count(Suggestion.id).label("count"),
            func.coalesce(func.sum(Suggestion.bytes_savings), 0).label("total_bytes"),
            func.count(Suggestion.id).filter(Suggestion.risk_level == "low").label("low_count"),
            func.count(Suggestion.id).filter(Suggestion.risk_level == "medium").label("medium_count"),
        ).where(
            Suggestion.user_id == current_user.id,
            Suggestion.dismissed == False,
            Suggestion.applied == False,
        )
    )
    row = result.one()

    return {
        "total_suggestions": row.count or 0,
        "total_savings_bytes": int(row.total_bytes),
        "low_risk_count": row.low_count or 0,
        "medium_risk_count": row.medium_count or 0,
    }


@router.post("/generate")
async def regenerate_suggestions(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run the rules engine and refresh suggestions."""
    suggestions = await generate_suggestions(db, current_user.id, replace_existing=True)
    await db.commit()

    return {
        "generated": len(suggestions),
        "total_savings_bytes": sum(s.bytes_savings for s in suggestions),
    }


@router.post("/{suggestion_id}/apply")
async def apply_suggestion_route(
    suggestion_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply a suggestion: soft-delete the files it identifies."""
    result = await apply_suggestion(db, suggestion_id, current_user.id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    await db.commit()
    return result


@router.post("/{suggestion_id}/dismiss")
async def dismiss_suggestion(
    suggestion_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a suggestion — it won't appear again until next scan."""
    result = await db.execute(
        select(Suggestion).where(
            Suggestion.id == suggestion_id,
            Suggestion.user_id == current_user.id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.dismissed = True
    await db.commit()

    return {"dismissed": True, "suggestion_id": suggestion_id}


def _serialize(s: Suggestion) -> dict:
    return {
        "id": s.id,
        "suggestion_type": s.suggestion_type,
        "title": s.title,
        "description": s.description,
        "file_count": len(s.file_ids) if s.file_ids else 0,
        "bytes_savings": s.bytes_savings,
        "risk_level": s.risk_level,
        "action": s.action,
        "action_label": s.action_label,
        "dismissed": s.dismissed,
        "applied": s.applied,
        "applied_at": s.applied_at,
        "created_at": s.created_at,
    }
