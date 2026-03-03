"""
OneDrive OAuth Routes — Month 3

GET /api/v1/connections/onedrive/authorize  → Microsoft OAuth URL
GET /api/v1/connections/onedrive/callback   → Token exchange + background index

Registered as a separate router and mounted alongside cloud.py routes.
"""

import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, encrypt_token
from app.models.user import User
from app.models.file import StorageConnection, ScanJob
from app.services.oauth.onedrive import (
    get_onedrive_auth_url, exchange_onedrive_code,
    get_onedrive_user_email, index_onedrive,
)

router = APIRouter(prefix="/connections", tags=["onedrive"])


@router.get("/onedrive/authorize")
async def onedrive_authorize(
    current_user: User = Depends(get_current_user),
):
    from fastapi import HTTPException
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="OneDrive integration requires Pro plan")
    state = f"{current_user.id}:{secrets.token_urlsafe(16)}"
    url = get_onedrive_auth_url(state)
    return {"url": url, "state": state}


@router.get("/onedrive/callback")
async def onedrive_callback(
    code: str = Query(...),
    state: str = Query(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    user_id = state.split(":")[0]
    token_data = await exchange_onedrive_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    email = await get_onedrive_user_email(access_token)

    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.user_id == user_id,
            StorageConnection.provider == "onedrive",
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
            provider="onedrive",
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
        background_tasks.add_task(_run_onedrive_index, conn.id, job.id, user_id)

    from app.core.config import settings
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL.rstrip('/')}/settings?connected=onedrive&job={job.id}",
        status_code=302,
    )


async def _run_onedrive_index(conn_id: str, job_id: str, user_id: str):
    from app.core.database import AsyncSessionLocal
    from app.services.scanning.duplicate_finder import find_exact_duplicates, persist_duplicate_groups

    async with AsyncSessionLocal() as db:
        try:
            conn_result = await db.execute(
                select(StorageConnection).where(StorageConnection.id == conn_id)
            )
            conn = conn_result.scalar_one()
            result = await index_onedrive(db, conn)

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
