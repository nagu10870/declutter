"""
Celery Tasks — Month 4

All long-running operations are defined here as Celery tasks.
Each task uses its own DB session (via AsyncSessionLocal) and handles
its own commit/rollback. Tasks are idempotent where possible.
"""

import asyncio
from datetime import datetime, timezone
from celery import shared_task
from app.services.workers.celery_app import celery_app


# ── Helper: run async code from sync Celery context ───────────────────────

def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ── Classification Tasks ──────────────────────────────────────────────────

@celery_app.task(name="app.services.workers.tasks.classify_user_files", bind=True, max_retries=3)
def classify_user_files(self, user_id: str, limit: int = 500, use_ai: bool = False):
    """
    Classify all unclassified files for a user.
    Called after indexing completes.
    """
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.ai.classifier import classify_files_batch
        from app.services.ai.suggestions_engine import generate_suggestions
        async with AsyncSessionLocal() as db:
            result = await classify_files_batch(db, user_id, limit=limit, use_ai=use_ai)
            await generate_suggestions(db, user_id)
            await db.commit()
            return result

    try:
        return run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


# ── CLIP Embedding Tasks ──────────────────────────────────────────────────

@celery_app.task(name="app.services.workers.tasks.generate_embeddings", bind=True, max_retries=2)
def generate_embeddings(self, user_id: str, limit: int = 200):
    """Generate CLIP embeddings for images without them."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.embeddings.clip_service import generate_embeddings_batch
        async with AsyncSessionLocal() as db:
            result = await generate_embeddings_batch(db, user_id, limit=limit)
            await db.commit()
            return result

    try:
        return run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


# ── Notification Tasks ────────────────────────────────────────────────────

@celery_app.task(name="app.services.workers.tasks.send_scan_complete_email")
def send_scan_complete_email(user_id: str, job_id: str):
    """Send scan completion email with digest."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.notifications.email_service import send_scan_digest
        from app.models.user import User
        from app.models.file import ScanJob
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            job_result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = job_result.scalar_one_or_none()
            if user and job:
                await send_scan_digest(user, job)

    run_async(_run())


@celery_app.task(name="app.services.workers.tasks.send_weekly_digest")
def send_weekly_digest(user_id: str):
    """Send weekly storage digest email."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.notifications.email_service import send_weekly_storage_digest
        from app.models.user import User
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                await send_weekly_storage_digest(db, user)

    run_async(_run())


# ── Scheduled Tasks ───────────────────────────────────────────────────────

@celery_app.task(name="app.services.workers.tasks.weekly_scan_all")
def weekly_scan_all():
    """Re-index all active cloud connections for all users."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.file import StorageConnection
        from app.models.user import User
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(StorageConnection, User)
                .join(User, User.id == StorageConnection.user_id)
                .where(
                    User.is_active == True,
                    StorageConnection.provider != "local",
                )
            )
            connections = result.all()
            # Trigger individual re-index tasks
            for conn, user in connections:
                if conn.provider == "google_drive":
                    from app.services.workers.tasks import reindex_connection
                    reindex_connection.delay(conn.id, user.id)

    run_async(_run())


@celery_app.task(name="app.services.workers.tasks.reindex_connection", bind=True, max_retries=2)
def reindex_connection(self, connection_id: str, user_id: str):
    """Re-index a single cloud connection."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.file import StorageConnection
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(StorageConnection).where(StorageConnection.id == connection_id)
            )
            conn = result.scalar_one_or_none()
            if not conn:
                return

            if conn.provider == "google_drive":
                from app.services.oauth.google_drive import index_google_drive
                await index_google_drive(db, conn)
            elif conn.provider == "dropbox":
                from app.services.oauth.dropbox import index_dropbox
                await index_dropbox(db, conn)
            elif conn.provider == "onedrive":
                from app.services.oauth.onedrive import index_onedrive
                await index_onedrive(db, conn)

            await db.commit()

    try:
        return run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="app.services.workers.tasks.send_monthly_reports")
def send_monthly_reports():
    """Send monthly storage reports to all Pro users."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.tier == "pro", User.is_active == True)
            )
            users = result.scalars().all()
            for user in users:
                send_weekly_digest.delay(user.id)

    run_async(_run())


@celery_app.task(name="app.services.workers.tasks.cleanup_expired_data")
def cleanup_expired_data():
    """Clean up expired OAuth states, old scan jobs, etc."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            # Delete expired OAuth state tokens
            await db.execute(text(
                "DELETE FROM oauth_states WHERE expires_at < NOW()"
            ))
            # Delete very old completed scan jobs (>90 days)
            await db.execute(text(
                "DELETE FROM scan_jobs WHERE status = 'completed' "
                "AND completed_at < NOW() - INTERVAL '90 days'"
            ))
            await db.commit()

    run_async(_run())
