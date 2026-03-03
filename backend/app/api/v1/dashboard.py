from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import FileRecord, ScanJob, DuplicateGroup, StorageConnection
from app.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Total files + size
    file_stats = await db.execute(
        select(
            func.count(FileRecord.id).label("total_files"),
            func.coalesce(func.sum(FileRecord.file_size), 0).label("total_size"),
        ).where(
            FileRecord.user_id == current_user.id,
            FileRecord.is_deleted == False,
        )
    )
    fs = file_stats.one()

    # Duplicate savings
    dup_stats = await db.execute(
        select(
            func.count(DuplicateGroup.id).label("dup_groups"),
            func.coalesce(func.sum(DuplicateGroup.total_wasted_bytes), 0).label("dup_bytes"),
        ).where(
            DuplicateGroup.user_id == current_user.id,
            DuplicateGroup.resolved == False,
        )
    )
    ds = dup_stats.one()

    # Last scan
    last_scan_result = await db.execute(
        select(ScanJob.completed_at)
        .where(
            ScanJob.user_id == current_user.id,
            ScanJob.status == "completed",
        )
        .order_by(ScanJob.completed_at.desc())
        .limit(1)
    )
    last_scan = last_scan_result.scalar_one_or_none()

    # Connection count
    conn_count_result = await db.execute(
        select(func.count(StorageConnection.id)).where(
            StorageConnection.user_id == current_user.id
        )
    )
    conn_count = conn_count_result.scalar() or 0

    # Approximate risk split: exact duplicates = low risk, large old files = medium
    low_risk = int(ds.dup_bytes * 0.7)
    review_needed = int(ds.dup_bytes * 0.3)

    return DashboardSummary(
        total_files=fs.total_files or 0,
        total_size_bytes=int(fs.total_size),
        potential_savings_bytes=int(ds.dup_bytes),
        low_risk_bytes=low_risk,
        review_needed_bytes=review_needed,
        duplicate_groups=ds.dup_groups or 0,
        last_scan=last_scan,
        storage_connections=conn_count,
    )
