"""
Similar Images Routes — Month 2

Uses perceptual hashing (pHash) to find visually similar photos
even when files are not byte-for-byte identical.

Use cases:
  - Same photo saved at different resolutions
  - Photo + edited version (cropped, brightened, filtered)
  - Screenshots of the same content taken at slightly different times
  - RAW + JPEG pairs

Gate: Pro users only (similarity detection is compute-intensive)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import FileRecord, CleanupAction
from app.services.scanning.duplicate_finder import find_similar_images
from app.services.thumbnails.service import get_thumbnail_url
from app.schemas import FileRecordResponse
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/similar", tags=["similar-images"])


@router.get("")
async def list_similar_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    threshold: int = Query(default=10, ge=1, le=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
):
    """
    Return groups of visually similar images using pHash clustering.
    Pro only — computationally intensive for large libraries.
    """
    if not current_user.is_pro:
        raise HTTPException(
            status_code=403,
            detail="Visual similarity detection requires Pro plan. "
                   "Upgrade to find near-duplicate and edited photos."
        )

    # Run pHash similarity clustering
    groups = await find_similar_images(db, current_user.id, threshold=threshold)

    # Paginate
    total = len(groups)
    start = (page - 1) * page_size
    page_groups = groups[start: start + page_size]

    # Enrich each group with full file details
    enriched = []
    for group in page_groups:
        file_ids = group["file_ids"]
        result = await db.execute(
            select(FileRecord).where(
                FileRecord.id.in_(file_ids),
                FileRecord.is_deleted == False,
            )
        )
        files = result.scalars().all()

        enriched.append({
            "match_type": group["match_type"],
            "similarity": group["similarity"],
            "wasted_bytes": group["wasted_bytes"],
            "files": [
                {
                    "id": f.id,
                    "file_name": f.file_name,
                    "file_path": f.file_path,
                    "file_size": f.file_size,
                    "mime_type": f.mime_type,
                    "last_modified": f.last_modified,
                    "thumbnail_url": get_thumbnail_url(f.thumbnail_key),
                    "perceptual_hash": f.perceptual_hash,
                }
                for f in files
            ],
        })

    return {
        "groups": enriched,
        "total_groups": total,
        "page": page,
        "page_size": page_size,
        "threshold_used": threshold,
    }


@router.get("/stats")
async def similar_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick summary: how many images have perceptual hashes, how many are similar."""
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Pro plan required")

    total_images = await db.execute(
        select(text("COUNT(*)")).select_from(FileRecord).where(
            FileRecord.user_id == current_user.id,
            FileRecord.mime_type.like("image/%"),
            FileRecord.is_deleted == False,
        )
    )
    images_with_hash = await db.execute(
        select(text("COUNT(*)")).select_from(FileRecord).where(
            FileRecord.user_id == current_user.id,
            FileRecord.mime_type.like("image/%"),
            FileRecord.perceptual_hash.isnot(None),
            FileRecord.is_deleted == False,
        )
    )

    groups = await find_similar_images(db, current_user.id)
    total_wasted = sum(g["wasted_bytes"] for g in groups)

    return {
        "total_images": total_images.scalar() or 0,
        "images_with_phash": images_with_hash.scalar() or 0,
        "similar_groups": len(groups),
        "wasted_bytes": total_wasted,
    }


@router.delete("/files/{file_id}")
async def delete_similar_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete one file from a similarity group, with undo support."""
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Pro plan required")

    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id,
            FileRecord.user_id == current_user.id,
            FileRecord.is_deleted == False,
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    action = CleanupAction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        file_id=file.id,
        action="delete",
        action_by="user",
        bytes_freed=file.file_size,
        undo_data={
            "file_path": file.file_path,
            "remote_id": file.remote_id,
            "connection_id": file.connection_id,
            "source": "similar_images",
        },
    )
    db.add(action)
    file.is_deleted = True

    return {
        "deleted": True,
        "file_id": file_id,
        "bytes_freed": file.file_size,
        "undo_action_id": action.id,
    }
