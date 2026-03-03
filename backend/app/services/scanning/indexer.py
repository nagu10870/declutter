"""
File Indexer Service

Accepts a batch of file metadata records (from client manifest or cloud API response)
and upserts them into file_records. No raw file bytes are ever stored.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models.file import FileRecord, ScanJob, StorageConnection
from app.services.scanning.duplicate_finder import (
    find_exact_duplicates, persist_duplicate_groups
)
import uuid
from pydantic import BaseModel


class FileManifestItem(BaseModel):
    """Single file entry from client or cloud provider."""
    remote_id: Optional[str] = None
    file_path: str
    file_name: str
    file_size: int
    mime_type: Optional[str] = None
    md5_hash: Optional[str] = None
    sha256_hash: Optional[str] = None
    perceptual_hash: Optional[str] = None
    last_modified: Optional[datetime] = None
    created_date: Optional[datetime] = None


class IndexerResult(BaseModel):
    files_indexed: int
    files_updated: int
    bytes_total: int
    duplicate_groups_found: int


async def index_file_manifest(
    db: AsyncSession,
    user_id: str,
    connection_id: str,
    job_id: str,
    manifest: list[FileManifestItem],
    run_dedup: bool = True,
) -> IndexerResult:
    """
    Upsert a batch of file records from a manifest.
    Called by the scan worker in chunks (e.g. 500 files at a time).
    """
    indexed = 0
    updated = 0
    bytes_total = 0

    for item in manifest:
        # Check if record exists (by remote_id or path)
        existing = None
        if item.remote_id:
            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.user_id == user_id,
                    FileRecord.connection_id == connection_id,
                    FileRecord.remote_id == item.remote_id,
                )
            )
            existing = result.scalar_one_or_none()

        if not existing and item.file_path:
            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.user_id == user_id,
                    FileRecord.connection_id == connection_id,
                    FileRecord.file_path == item.file_path,
                )
            )
            existing = result.scalar_one_or_none()

        if existing:
            # Update hash/size if changed
            existing.file_size = item.file_size
            existing.md5_hash = item.md5_hash or existing.md5_hash
            existing.sha256_hash = item.sha256_hash or existing.sha256_hash
            existing.perceptual_hash = item.perceptual_hash or existing.perceptual_hash
            existing.last_modified = item.last_modified
            existing.is_deleted = False
            existing.indexed_at = datetime.now(timezone.utc)
            updated += 1
        else:
            record = FileRecord(
                id=str(uuid.uuid4()),
                user_id=user_id,
                connection_id=connection_id,
                remote_id=item.remote_id,
                file_path=item.file_path,
                file_name=item.file_name,
                file_size=item.file_size,
                mime_type=item.mime_type,
                md5_hash=item.md5_hash,
                sha256_hash=item.sha256_hash,
                perceptual_hash=item.perceptual_hash,
                last_modified=item.last_modified,
                created_date=item.created_date,
            )
            db.add(record)
            indexed += 1

        bytes_total += item.file_size

    await db.flush()

    # Update scan job progress
    result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = result.scalar_one_or_none()
    if job:
        job.files_scanned = (job.files_scanned or 0) + len(manifest)
        job.bytes_reclaimable = 0  # Will be updated after dedup

    # Run duplicate detection after indexing
    dup_groups = []
    if run_dedup:
        dup_groups = await find_exact_duplicates(db, user_id)
        await persist_duplicate_groups(db, user_id, dup_groups)

        if job:
            job.bytes_reclaimable = sum(g["wasted_bytes"] for g in dup_groups)

    await db.flush()

    return IndexerResult(
        files_indexed=indexed,
        files_updated=updated,
        bytes_total=bytes_total,
        duplicate_groups_found=len(dup_groups),
    )


async def mark_files_deleted(
    db: AsyncSession,
    user_id: str,
    connection_id: str,
    file_ids: list[str],
):
    """Mark files as logically deleted (soft delete)."""
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.user_id == user_id,
            FileRecord.connection_id == connection_id,
            FileRecord.id.in_(file_ids),
        )
    )
    for f in result.scalars().all():
        f.is_deleted = True
