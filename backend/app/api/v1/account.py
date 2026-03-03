"""
Account Management Routes — Month 6

GET    /api/v1/account/preferences        → Get user preferences
PUT    /api/v1/account/preferences        → Update preferences  
DELETE /api/v1/account                    → Delete account + all data (GDPR right to erasure)
POST   /api/v1/account/password           → Change password
GET    /api/v1/account/stats              → Personal usage stats over time
POST   /api/v1/account/notification-prefs → Email notification preferences
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash, verify_password
from app.models.user import User
from app.models.file import FileRecord, ScanJob, StorageConnection, CleanupAction

router = APIRouter(prefix="/account", tags=["account"])


class PreferencesRequest(BaseModel):
    email_scan_digest: bool = True
    email_weekly_report: bool = True
    email_trial_reminders: bool = True
    email_product_updates: bool = False
    default_threshold: int = 10   # pHash similarity
    auto_classify: bool = True     # Classify files after each scan
    timezone: str = "UTC"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    confirm_email: str  # Must match user's email
    reason: Optional[str] = None


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user preferences (stored as JSON in user.preferences column)."""
    prefs = getattr(current_user, "preferences", None) or {}
    defaults = PreferencesRequest()
    return {
        "email_scan_digest": prefs.get("email_scan_digest", defaults.email_scan_digest),
        "email_weekly_report": prefs.get("email_weekly_report", defaults.email_weekly_report),
        "email_trial_reminders": prefs.get("email_trial_reminders", defaults.email_trial_reminders),
        "email_product_updates": prefs.get("email_product_updates", defaults.email_product_updates),
        "default_threshold": prefs.get("default_threshold", defaults.default_threshold),
        "auto_classify": prefs.get("auto_classify", defaults.auto_classify),
        "timezone": prefs.get("timezone", defaults.timezone),
    }


@router.put("/preferences")
async def update_preferences(
    req: PreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not hasattr(current_user, "preferences"):
        raise HTTPException(status_code=500, detail="Preferences column not migrated yet")
    current_user.preferences = req.model_dump()
    await db.commit()
    return {"updated": True, "preferences": req.model_dump()}


@router.post("/password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    current_user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return {"changed": True}


@router.get("/stats")
async def account_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Personal usage statistics over time."""
    # Monthly file counts for the last 6 months
    monthly = await db.execute(
        text("""
            SELECT
                DATE_TRUNC('month', indexed_at) AS month,
                COUNT(*) AS files_added,
                COALESCE(SUM(file_size), 0) AS bytes_added
            FROM file_records
            WHERE user_id = :uid AND is_deleted = FALSE
              AND indexed_at > NOW() - INTERVAL '6 months'
            GROUP BY month
            ORDER BY month
        """),
        {"uid": current_user.id}
    )
    months = [
        {
            "month": row.month.strftime("%Y-%m"),
            "files_added": row.files_added,
            "bytes_added": row.bytes_added,
        }
        for row in monthly
    ]

    # All-time totals
    totals = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_files,
                COALESCE(SUM(file_size), 0) as total_bytes,
                COUNT(*) FILTER (WHERE is_deleted = TRUE) as deleted_files
            FROM file_records
            WHERE user_id = :uid
        """),
        {"uid": current_user.id}
    )
    t = totals.one()

    # Cleanup actions
    actions = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_cleanups,
                COALESCE(SUM(bytes_freed), 0) as total_freed
            FROM cleanup_actions
            WHERE user_id = :uid AND undone_at IS NULL
        """),
        {"uid": current_user.id}
    )
    a = actions.one()

    return {
        "monthly_breakdown": months,
        "totals": {
            "total_files": t.total_files,
            "total_bytes": t.total_bytes,
            "deleted_files": t.deleted_files,
            "total_cleanups": a.total_cleanups,
            "total_bytes_freed": a.total_freed,
        },
        "member_since": current_user.created_at,
    }


@router.delete("")
async def delete_account(
    req: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GDPR Right to Erasure: permanently delete account and all data.
    Requires email confirmation to prevent accidents.
    """
    if req.confirm_email.lower() != current_user.email.lower():
        raise HTTPException(status_code=400, detail="Email confirmation doesn't match")

    # Cancel Stripe subscription if Pro
    if current_user.is_pro and current_user.stripe_customer_id:
        try:
            import stripe
            from app.core.config import settings
            if settings.STRIPE_SECRET_KEY:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                subs = stripe.Subscription.list(
                    customer=current_user.stripe_customer_id,
                    status="active",
                )
                for sub in subs.data:
                    stripe.Subscription.cancel(sub.id)
        except Exception:
            pass  # Don't block deletion if Stripe call fails

    # Hard delete — cascade will handle all related records
    await db.delete(current_user)
    await db.commit()

    return {
        "deleted": True,
        "message": "Account and all associated data have been permanently deleted.",
    }
