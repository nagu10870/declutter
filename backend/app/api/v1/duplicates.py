from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import DuplicateGroup, FileRecord, CleanupAction
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import uuid

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


class ResolveAction(BaseModel):
    action: str  # keep_first, keep_largest, keep_newest, delete_all_except
    keep_file_id: Optional[str] = None  # for delete_all_except


@router.get("")
async def list_duplicate_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    match_type: Optional[str] = None,  # exact, similar, fuzzy
    page: int = 1,
    page_size: int = 20,
):
    query = select(DuplicateGroup).where(
        DuplicateGroup.user_id == current_user.id,
        DuplicateGroup.resolved == False,
    )
    if match_type:
        query = query.where(DuplicateGroup.match_type == match_type)

    query = query.order_by(DuplicateGroup.total_wasted_bytes.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    groups = result.scalars().all()

    enriched = []
    for group in groups:
        # Fetch associated file records via raw query
        # (In production, add a proper join table)
        files_result = await db.execute(
            text("""
                SELECT id, file_name, file_path, file_size, mime_type,
                       last_modified, md5_hash
                FROM file_records
                WHERE user_id = :uid
                  AND is_deleted = FALSE
                  AND md5_hash = (
                      SELECT md5_hash FROM file_records
                      WHERE id = (
                          SELECT file_records.id FROM file_records
                          WHERE user_id = :uid
                            AND is_deleted = FALSE
                          LIMIT 1
                      )
                  )
                LIMIT 20
            """),
            {"uid": current_user.id}
        )

        enriched.append({
            "id": group.id,
            "match_type": group.match_type,
            "similarity": group.similarity,
            "total_wasted_bytes": group.total_wasted_bytes,
            "resolved": group.resolved,
            "created_at": group.created_at,
        })

    return {"groups": enriched, "page": page, "page_size": page_size}


@router.get("/files")
async def list_duplicate_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 50,
):
    """
    Returns files grouped by MD5 hash with wasted bytes calculation.
    This is the primary view for the duplicates page.
    """
    result = await db.execute(
        text("""
            SELECT
                md5_hash,
                COUNT(*) AS file_count,
                SUM(file_size) - MIN(file_size) AS wasted_bytes,
                json_agg(json_build_object(
                    'id', id,
                    'file_name', file_name,
                    'file_path', file_path,
                    'file_size', file_size,
                    'mime_type', mime_type,
                    'last_modified', last_modified
                ) ORDER BY indexed_at ASC) AS files
            FROM file_records
            WHERE user_id = :user_id
              AND is_deleted = FALSE
              AND md5_hash IS NOT NULL
            GROUP BY md5_hash
            HAVING COUNT(*) > 1
            ORDER BY wasted_bytes DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "user_id": current_user.id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
    )
    groups = [dict(r) for r in result.mappings()]
    return {"groups": groups, "page": page, "page_size": page_size}


@router.post("/{group_id}/resolve")
async def resolve_duplicate_group(
    group_id: str,
    body: ResolveAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DuplicateGroup).where(
            DuplicateGroup.id == group_id,
            DuplicateGroup.user_id == current_user.id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Duplicate group not found")

    # Find all files in this group by matching hash
    # (simplified: in production use proper join table)
    group.resolved = True
    group.resolved_at = datetime.now(timezone.utc)

    return {"message": "Group resolved", "group_id": group_id}


@router.delete("/files/{file_id}")
async def delete_duplicate_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a specific duplicate file as deleted. Records undo data."""
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

    # Record cleanup action for undo
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
        },
    )
    db.add(action)
    file.is_deleted = True

    return {
        "message": "File marked for deletion",
        "file_id": file_id,
        "bytes_freed": file.file_size,
        "undo_action_id": action.id,
    }


@router.post("/files/{file_id}/undo")
async def undo_delete(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id,
            FileRecord.user_id == current_user.id,
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    file.is_deleted = False
    return {"message": "File restored", "file_id": file_id}
