from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import ScanJob, StorageConnection, DuplicateGroup, FileRecord
from app.schemas import ScanJobResponse
from app.services.scanning.indexer import index_file_manifest, FileManifestItem
from app.services.scanning.duplicate_finder import find_exact_duplicates
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
import uuid
import asyncio
import json

router = APIRouter(prefix="/scans", tags=["scans"])


class StartScanRequest(BaseModel):
    connection_id: str
    scan_type: str = "full"  # full, incremental, duplicates_only
    files_total: Optional[int] = None


class ManifestChunkRequest(BaseModel):
    job_id: str
    files: list[FileManifestItem]
    is_final_chunk: bool = False


@router.post("", response_model=ScanJobResponse, status_code=201)
async def start_scan(
    body: StartScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scan job. Client will push manifest chunks to /scans/ingest."""

    # Free tier: max 1 active scan
    if not current_user.is_pro:
        active_result = await db.execute(
            select(func.count(ScanJob.id)).where(
                ScanJob.user_id == current_user.id,
                ScanJob.status.in_(["queued", "running"]),
            )
        )
        if (active_result.scalar() or 0) >= 1:
            raise HTTPException(
                status_code=429, detail="Free tier allows 1 active scan. Upgrade to Pro."
            )

    # Verify connection belongs to user
    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.id == body.connection_id,
            StorageConnection.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Connection not found")

    job = ScanJob(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        connection_id=body.connection_id,
        scan_type=body.scan_type,
        status="running",
        files_total=body.files_total,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


@router.post("/ingest")
async def ingest_manifest_chunk(
    body: ManifestChunkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Client pushes batches of file metadata here.
    No file bytes ever sent — only names, sizes, hashes, paths.
    """
    result = await db.execute(
        select(ScanJob).where(
            ScanJob.id == body.job_id,
            ScanJob.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    if job.status not in ("running", "queued"):
        raise HTTPException(status_code=409, detail=f"Job is {job.status}, not accepting data")

    indexer_result = await index_file_manifest(
        db=db,
        user_id=current_user.id,
        connection_id=job.connection_id,
        job_id=body.job_id,
        manifest=body.files,
        run_dedup=body.is_final_chunk,
    )

    if body.is_final_chunk:
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)

    return {
        "job_id": body.job_id,
        "files_indexed": indexer_result.files_indexed,
        "files_updated": indexer_result.files_updated,
        "duplicate_groups_found": indexer_result.duplicate_groups_found,
        "bytes_reclaimable": job.bytes_reclaimable,
        "status": job.status,
    }


@router.get("/{job_id}", response_model=ScanJobResponse)
async def get_scan_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScanJob).where(
            ScanJob.id == job_id,
            ScanJob.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job


@router.get("/{job_id}/stream")
async def stream_scan_progress(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events endpoint for live scan progress."""

    async def event_generator():
        while True:
            result = await db.execute(
                select(ScanJob).where(
                    ScanJob.id == job_id,
                    ScanJob.user_id == current_user.id,
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break

            payload = {
                "status": job.status,
                "files_scanned": job.files_scanned,
                "files_total": job.files_total,
                "progress_pct": job.progress_pct,
                "bytes_reclaimable": job.bytes_reclaimable,
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if job.status in ("completed", "failed"):
                break

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[ScanJobResponse])
async def list_scans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    result = await db.execute(
        select(ScanJob)
        .where(ScanJob.user_id == current_user.id)
        .order_by(ScanJob.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
