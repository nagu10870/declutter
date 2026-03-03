"""
Admin Routes — Month 5

Admin-only endpoints for monitoring and user management.
Requires: user.tier == "admin" (set manually in DB) OR ADMIN_SECRET header.

GET  /api/v1/admin/stats         → Platform-wide stats
GET  /api/v1/admin/users         → List all users
GET  /api/v1/admin/users/{id}    → User detail
POST /api/v1/admin/users/{id}/tier → Change user tier
GET  /api/v1/admin/audit         → Audit log viewer
"""

import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import FileRecord, ScanJob, StorageConnection
from app.models.extended import AuditLog

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


async def require_admin(
    current_user: User = Depends(get_current_user),
    x_admin_secret: Optional[str] = Header(default=None),
):
    is_admin_tier = current_user.tier == "admin"
    is_secret_auth = ADMIN_SECRET and x_admin_secret == ADMIN_SECRET
    if not is_admin_tier and not is_secret_auth:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/stats")
async def platform_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Platform-wide KPI dashboard."""
    stats = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_users,
                COUNT(*) FILTER (WHERE tier = 'pro') as pro_users,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as new_users_30d,
                COUNT(*) FILTER (WHERE is_active = TRUE) as active_users
            FROM users
        """)
    )
    users_row = stats.one()

    files_stats = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_files,
                COALESCE(SUM(file_size), 0) as total_bytes,
                COUNT(*) FILTER (WHERE indexed_at > NOW() - INTERVAL '24 hours') as indexed_today
            FROM file_records
            WHERE is_deleted = FALSE
        """)
    )
    files_row = files_stats.one()

    scan_stats = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_scans,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_scans,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as scans_today
            FROM scan_jobs
        """)
    )
    scans_row = scan_stats.one()

    return {
        "users": {
            "total": users_row.total_users,
            "pro": users_row.pro_users,
            "free": users_row.total_users - users_row.pro_users,
            "new_30d": users_row.new_users_30d,
            "active": users_row.active_users,
            "conversion_rate": round(
                (users_row.pro_users / max(users_row.total_users, 1)) * 100, 1
            ),
        },
        "files": {
            "total": files_row.total_files,
            "total_bytes": files_row.total_bytes,
            "indexed_today": files_row.indexed_today,
        },
        "scans": {
            "total": scans_row.total_scans,
            "completed": scans_row.completed_scans,
            "today": scans_row.scans_today,
        },
    }


@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(User.email.ilike(f"%{search}%"))
    if tier:
        q = q.where(User.tier == tier)

    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar() or 0

    q = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    users = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "tier": u.tier,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in users
        ],
    }


class ChangeTierRequest(BaseModel):
    tier: str  # "free" | "pro" | "admin"


@router.post("/users/{user_id}/tier")
async def change_user_tier(
    user_id: str,
    req: ChangeTierRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if req.tier not in ("free", "pro", "admin"):
        raise HTTPException(status_code=400, detail="Invalid tier")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_tier = user.tier
    user.tier = req.tier

    # Log to audit trail
    log = AuditLog(
        user_id=current_user.id,
        action="admin.change_tier",
        resource_type="user",
        resource_id=user_id,
        metadata={"old_tier": old_tier, "new_tier": req.tier},
    )
    db.add(log)
    await db.commit()

    return {"user_id": user_id, "old_tier": old_tier, "new_tier": req.tier}


@router.get("/audit")
async def audit_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    user_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))

    q = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    logs = (await db.execute(q)).scalars().all()

    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "metadata": l.metadata,
            "ip_address": l.ip_address,
            "created_at": l.created_at,
        }
        for l in logs
    ]
