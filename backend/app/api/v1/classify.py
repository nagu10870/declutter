"""
AI Classification Routes — Month 3

POST /api/v1/classify/run          → Trigger batch classification on user's files
GET  /api/v1/classify/stats        → Classification breakdown (categories, counts)
GET  /api/v1/classify/files        → Browse files filtered by category/tag
GET  /api/v1/classify/files/{id}   → Single file classification detail
"""

from fastapi import APIRouter, Depends, BackgroundTasks, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.file import FileRecord, FileClassification
from app.services.ai.classifier import classify_files_batch

router = APIRouter(prefix="/classify", tags=["classification"])


@router.post("/run")
async def run_classification(
    background_tasks: BackgroundTasks,
    use_ai: bool = Query(default=False, description="Use GPT-4o for ambiguous images (Pro + OpenAI key required)"),
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger file classification for the current user.
    Heuristics run synchronously (fast). GPT-4o runs in background (slow).
    """
    if use_ai and not current_user.is_pro:
        raise HTTPException(status_code=403, detail="AI classification requires Pro plan")

    if use_ai:
        # Long-running — run in background
        background_tasks.add_task(
            _run_classify_background, current_user.id, limit, True
        )
        return {"status": "started", "mode": "ai", "message": "AI classification running in background"}

    # Heuristics are fast — run inline
    result = await classify_files_batch(db, current_user.id, limit=limit, use_ai=False)
    await db.commit()

    # After classifying, regenerate suggestions
    background_tasks.add_task(_regenerate_suggestions, current_user.id)

    return {
        "status": "completed",
        "mode": "heuristic",
        "classified": result["classified"],
        "ai_classified": result["ai_classified"],
    }


@router.get("/stats")
async def classification_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Classification breakdown: how many files in each category."""
    # Category counts
    cat_result = await db.execute(
        text("""
            SELECT fc.category, COUNT(*) as count, SUM(fr.file_size) as total_bytes
            FROM file_classifications fc
            JOIN file_records fr ON fr.id = fc.file_id
            WHERE fc.user_id = :uid AND fr.is_deleted = FALSE
            GROUP BY fc.category
            ORDER BY count DESC
        """),
        {"uid": current_user.id},
    )
    categories = [
        {"category": r["category"] or "other", "count": r["count"], "total_bytes": r["total_bytes"] or 0}
        for r in cat_result.mappings()
    ]

    # Quality signals
    quality_result = await db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE fc.is_blurry = TRUE) as blurry_count,
                COUNT(*) FILTER (WHERE fc.is_screenshot = TRUE) as screenshot_count,
                COUNT(*) as total_classified,
                SUM(fr.file_size) FILTER (WHERE fc.is_blurry = TRUE) as blurry_bytes,
                SUM(fr.file_size) FILTER (WHERE fc.is_screenshot = TRUE) as screenshot_bytes
            FROM file_classifications fc
            JOIN file_records fr ON fr.id = fc.file_id
            WHERE fc.user_id = :uid AND fr.is_deleted = FALSE
        """),
        {"uid": current_user.id},
    )
    quality = quality_result.mappings().one()

    # Unclassified count
    classified_ids = select(FileClassification.file_id).where(
        FileClassification.user_id == current_user.id
    ).scalar_subquery()
    unclassified_result = await db.execute(
        select(func.count(FileRecord.id)).where(
            FileRecord.user_id == current_user.id,
            FileRecord.is_deleted == False,
            FileRecord.id.notin_(classified_ids),
        )
    )
    unclassified = unclassified_result.scalar() or 0

    return {
        "categories": categories,
        "total_classified": quality["total_classified"] or 0,
        "total_unclassified": unclassified,
        "blurry_count": quality["blurry_count"] or 0,
        "blurry_bytes": quality["blurry_bytes"] or 0,
        "screenshot_count": quality["screenshot_count"] or 0,
        "screenshot_bytes": quality["screenshot_bytes"] or 0,
    }


@router.get("/files")
async def classified_files(
    category: str | None = Query(default=None),
    is_blurry: bool | None = Query(default=None),
    is_screenshot: bool | None = Query(default=None),
    tag: str | None = Query(default=None, description="Filter by tag (e.g. 'receipt', 'blurry')"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse classified files with filters."""
    q = (
        select(FileRecord, FileClassification)
        .join(FileClassification, FileClassification.file_id == FileRecord.id)
        .where(
            FileRecord.user_id == current_user.id,
            FileRecord.is_deleted == False,
        )
    )
    if category:
        q = q.where(FileClassification.category == category)
    if is_blurry is not None:
        q = q.where(FileClassification.is_blurry == is_blurry)
    if is_screenshot is not None:
        q = q.where(FileClassification.is_screenshot == is_screenshot)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(FileRecord.file_size.desc())
    rows = (await db.execute(q)).all()

    files = []
    for record, classification in rows:
        # Tag filter (JSON array contains check)
        if tag and (not classification.tags or tag not in classification.tags):
            continue
        files.append({
            "id": record.id,
            "file_name": record.file_name,
            "file_path": record.file_path,
            "file_size": record.file_size,
            "mime_type": record.mime_type,
            "last_modified": record.last_modified,
            "thumbnail_key": record.thumbnail_key,
            "category": classification.category,
            "sub_category": classification.sub_category,
            "tags": classification.tags or [],
            "is_blurry": classification.is_blurry,
            "blur_score": classification.blur_score,
            "is_screenshot": classification.is_screenshot,
            "confidence": classification.confidence,
            "model_version": classification.model_version,
        })

    return {
        "files": files,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/files/{file_id}")
async def get_file_classification(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get classification details for a single file."""
    result = await db.execute(
        select(FileRecord, FileClassification)
        .outerjoin(FileClassification, FileClassification.file_id == FileRecord.id)
        .where(
            FileRecord.id == file_id,
            FileRecord.user_id == current_user.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    record, classification = row
    return {
        "file": {
            "id": record.id,
            "file_name": record.file_name,
            "file_path": record.file_path,
            "file_size": record.file_size,
            "mime_type": record.mime_type,
        },
        "classification": {
            "category": classification.category if classification else None,
            "sub_category": classification.sub_category if classification else None,
            "tags": classification.tags if classification else [],
            "is_blurry": classification.is_blurry if classification else None,
            "blur_score": classification.blur_score if classification else None,
            "is_screenshot": classification.is_screenshot if classification else None,
            "confidence": classification.confidence if classification else None,
            "model_version": classification.model_version if classification else None,
            "classified_at": classification.classified_at if classification else None,
        } if classification else None,
    }


# ── Background helpers ────────────────────────────────────────────────────

async def _run_classify_background(user_id: str, limit: int, use_ai: bool):
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await classify_files_batch(db, user_id, limit=limit, use_ai=use_ai)
            await db.commit()
            await _regenerate_suggestions(user_id)
        except Exception:
            pass


async def _regenerate_suggestions(user_id: str):
    from app.core.database import AsyncSessionLocal
    from app.services.ai.suggestions_engine import generate_suggestions
    async with AsyncSessionLocal() as db:
        try:
            await generate_suggestions(db, user_id)
            await db.commit()
        except Exception:
            pass
