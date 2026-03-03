from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import StorageConnection, FileRecord
from app.schemas import StorageConnectionResponse
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=list[StorageConnectionResponse])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StorageConnection).where(StorageConnection.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.id == connection_id,
            StorageConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    await db.delete(conn)


@router.get("/{connection_id}/usage")
async def get_usage(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.id == connection_id,
            StorageConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Count files for this connection
    file_count_result = await db.execute(
        select(func.count(FileRecord.id)).where(
            FileRecord.connection_id == connection_id,
            FileRecord.is_deleted == False,
        )
    )
    file_count = file_count_result.scalar() or 0

    total_size_result = await db.execute(
        select(func.sum(FileRecord.file_size)).where(
            FileRecord.connection_id == connection_id,
            FileRecord.is_deleted == False,
        )
    )
    total_size = total_size_result.scalar() or 0

    return {
        "connection_id": connection_id,
        "provider": conn.provider,
        "account_email": conn.account_email,
        "total_bytes": conn.total_bytes,
        "used_bytes": conn.used_bytes,
        "indexed_files": file_count,
        "indexed_size_bytes": total_size,
        "last_synced": conn.last_synced,
    }


# ── Local "connection" seeder (for MVP local scan) ─────────────────────────

@router.post("/local", response_model=StorageConnectionResponse, status_code=201)
async def add_local_connection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a local storage connection slot (scanning happens client-side)."""
    # Check if one already exists
    result = await db.execute(
        select(StorageConnection).where(
            StorageConnection.user_id == current_user.id,
            StorageConnection.provider == "local",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    conn = StorageConnection(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        provider="local",
        account_email=None,
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    return conn
