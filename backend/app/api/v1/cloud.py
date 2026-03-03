"""
Cloud OAuth Routes — Month 2

Endpoints:
  GET  /api/v1/connections/google/authorize      → redirect to Google
  GET  /api/v1/connections/google/callback       → code exchange + index
  GET  /api/v1/connections/dropbox/authorize     → redirect to Dropbox
  GET  /api/v1/connections/dropbox/callback      → code exchange + index
  POST /api/v1/connections/{id}/sync             → re-sync existing connection
  GET  /api/v1/connections/{id}/sync-status      → check index job progress
"""

import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, encrypt_token
from app.models.user import User
from app.models.file import StorageConnection, ScanJob
from app.services.oauth.google_drive import (
    get_google_auth_url, exchange_google_code,
    get_google_user_email, index_google_drive,
)
from app.services.oauth.dropbox import (
    get_dropbox_auth_url, exchange_dropbox_code,
    get_dropbox_account_email, index_dropbox,
)

router = APIRouter(prefix="/connections", tags=["cloud-connections"])


# ── Google Drive ───────────────────────────────────────────────────────────

@router.get("/google/authorize")
async def google_authorize(
    current_user: User = Depends(get_current_user),
):
    """Return the Google OAuth URL. Frontend opens this in a popup/redirect."""
    if not current_user.is_pro:
        raise HTTPException(
            status_code=403,
            detail="Google Drive integration requires Pro plan"
        )
    state = f"{current_user.id}:{secrets.token_urlsafe(16)}"
    url = get_google_auth_url(state)
    return {"url": url, "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Google redirects here after user grants access.
    Exchanges code → tokens → creates connection → starts background index.
    """
    user_id = state.split(":")[0]

    # Exchange code for tokens
    token_data = await exchange_google_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    email = await get_google_user_email(access_token)

    # Check if connection already exists for this email
    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.user_id == user_id,
            StorageConnection.provider == "google_drive",
            StorageConnection.account_email == email,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update tokens
        existing.oauth_token_enc = encrypt_token(access_token)
        if refresh_token:
            existing.refresh_token_enc = encrypt_token(refresh_token)
        conn = existing
    else:
        conn = StorageConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider="google_drive",
            oauth_token_enc=encrypt_token(access_token),
            refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
            account_email=email,
        )
        db.add(conn)

    await db.flush()
    await db.refresh(conn)

    # Create scan job to track indexing
    job = ScanJob(
        id=str(uuid.uuid4()),
        user_id=user_id,
        connection_id=conn.id,
        scan_type="full",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    # Run indexing in background
    if background_tasks:
        background_tasks.add_task(_run_google_index, conn.id, job.id, user_id)

    # Redirect back to frontend settings page
    return RedirectResponse(
        url=f"{_frontend_url()}/settings?connected=google&job={job.id}",
        status_code=302,
    )


async def _run_google_index(conn_id: str, job_id: str, user_id: str):
    """Background task: index all Google Drive files."""
    from app.core.database import AsyncSessionLocal
    from app.services.scanning.duplicate_finder import find_exact_duplicates, persist_duplicate_groups

    async with AsyncSessionLocal() as db:
        try:
            conn_result = await db.execute(
                select(StorageConnection).where(StorageConnection.id == conn_id)
            )
            conn = conn_result.scalar_one()

            result = await index_google_drive(db, conn)

            # Run duplicate detection
            dup_groups = await find_exact_duplicates(db, user_id)
            await persist_duplicate_groups(db, user_id, dup_groups)

            job_result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = job_result.scalar_one()
            job.status = "completed"
            job.files_scanned = result["files_indexed"] + result["files_updated"]
            job.bytes_reclaimable = sum(g["wasted_bytes"] for g in dup_groups)
            job.completed_at = datetime.now(timezone.utc)

            await db.commit()
        except Exception as e:
            async with AsyncSessionLocal() as err_db:
                job_result = await err_db.execute(select(ScanJob).where(ScanJob.id == job_id))
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await err_db.commit()


# ── Dropbox ────────────────────────────────────────────────────────────────

@router.get("/dropbox/authorize")
async def dropbox_authorize(
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Dropbox integration requires Pro plan")
    state = f"{current_user.id}:{secrets.token_urlsafe(16)}"
    url = get_dropbox_auth_url(state)
    return {"url": url, "state": state}


@router.get("/dropbox/callback")
async def dropbox_callback(
    code: str = Query(...),
    state: str = Query(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    user_id = state.split(":")[0]
    token_data = await exchange_dropbox_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    email = await get_dropbox_account_email(access_token)

    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.user_id == user_id,
            StorageConnection.provider == "dropbox",
            StorageConnection.account_email == email,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.oauth_token_enc = encrypt_token(access_token)
        if refresh_token:
            existing.refresh_token_enc = encrypt_token(refresh_token)
        conn = existing
    else:
        conn = StorageConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider="dropbox",
            oauth_token_enc=encrypt_token(access_token),
            refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
            account_email=email,
        )
        db.add(conn)

    await db.flush()
    await db.refresh(conn)

    job = ScanJob(
        id=str(uuid.uuid4()),
        user_id=user_id,
        connection_id=conn.id,
        scan_type="full",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    if background_tasks:
        background_tasks.add_task(_run_dropbox_index, conn.id, job.id, user_id)

    return RedirectResponse(
        url=f"{_frontend_url()}/settings?connected=dropbox&job={job.id}",
        status_code=302,
    )


async def _run_dropbox_index(conn_id: str, job_id: str, user_id: str):
    from app.core.database import AsyncSessionLocal
    from app.services.scanning.duplicate_finder import find_exact_duplicates, persist_duplicate_groups

    async with AsyncSessionLocal() as db:
        try:
            conn_result = await db.execute(
                select(StorageConnection).where(StorageConnection.id == conn_id)
            )
            conn = conn_result.scalar_one()
            result = await index_dropbox(db, conn)

            dup_groups = await find_exact_duplicates(db, user_id)
            await persist_duplicate_groups(db, user_id, dup_groups)

            job_result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = job_result.scalar_one()
            job.status = "completed"
            job.files_scanned = result["files_indexed"] + result["files_updated"]
            job.bytes_reclaimable = sum(g["wasted_bytes"] for g in dup_groups)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            async with AsyncSessionLocal() as err_db:
                job_result = await err_db.execute(select(ScanJob).where(ScanJob.id == job_id))
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await err_db.commit()


# ── Re-sync existing connection ────────────────────────────────────────────

@router.post("/{connection_id}/sync")
async def sync_connection(
    connection_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a re-index of an existing cloud connection."""
    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.id == connection_id,
            StorageConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    if conn.provider == "local":
        raise HTTPException(status_code=400, detail="Local connections use client-side scanning")

    job = ScanJob(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        connection_id=conn.id,
        scan_type="incremental",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    if conn.provider == "google_drive":
        background_tasks.add_task(_run_google_index, conn.id, job.id, current_user.id)
    elif conn.provider == "dropbox":
        background_tasks.add_task(_run_dropbox_index, conn.id, job.id, current_user.id)

    return {"job_id": job.id, "status": "running", "provider": conn.provider}


def _frontend_url() -> str:
    from app.core.config import settings
    return settings.FRONTEND_URL.rstrip("/")
