"""
Smart Suggestions Engine — Month 3

Generates actionable cleanup cards from indexed + classified files.
Each rule produces a Suggestion with:
  - title: plain-English description
  - description: what it is and why to clean it
  - file_ids: specific files this applies to
  - bytes_savings: how much space you'd reclaim
  - risk_level: "low" | "medium" | "high"
  - action: what to do (delete, archive, move)

Rules are sorted: low-risk biggest-savings first.
Suggestions are cached in DB and regenerated after each scan/classify cycle.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func

from app.models.file import FileRecord, FileClassification, Suggestion


# ── Rule Definitions ───────────────────────────────────────────────────────

RULES = [
    {
        "type": "old_screenshots",
        "risk": "low",
        "action": "delete",
        "action_label": "Delete Screenshots",
        "title_fn": lambda n, b: f"{n} old screenshots",
        "desc_fn": lambda n, b: (
            f"These {n} screenshots haven't been accessed in 6+ months and are taking up "
            f"{_fmt(b)}. Screenshots are usually captured for one-time reference and safe to delete."
        ),
        "query": """
            SELECT fr.id, fr.file_size
            FROM file_records fr
            JOIN file_classifications fc ON fc.file_id = fr.id
            WHERE fr.user_id = :uid
              AND fc.is_screenshot = TRUE
              AND fr.last_modified < NOW() - INTERVAL '6 months'
              AND fr.is_deleted = FALSE
            ORDER BY fr.file_size DESC
            LIMIT 1000
        """,
    },
    {
        "type": "blurry_photos",
        "risk": "low",
        "action": "delete",
        "action_label": "Delete Blurry Photos",
        "title_fn": lambda n, b: f"{n} blurry photos detected",
        "desc_fn": lambda n, b: (
            f"{n} photos were detected as out-of-focus or blurry using blur analysis. "
            f"Freeing {_fmt(b)}."
        ),
        "query": """
            SELECT fr.id, fr.file_size
            FROM file_records fr
            JOIN file_classifications fc ON fc.file_id = fr.id
            WHERE fr.user_id = :uid
              AND fc.is_blurry = TRUE
              AND fr.is_deleted = FALSE
            ORDER BY fr.file_size DESC
            LIMIT 500
        """,
    },
    {
        "type": "receipt_archive",
        "risk": "medium",
        "action": "archive",
        "action_label": "Move to Finance Folder",
        "title_fn": lambda n, b: f"{n} receipts & invoices to organize",
        "desc_fn": lambda n, b: (
            f"Found {n} files that look like receipts or invoices ({_fmt(b)}). "
            f"Moving them to a Finance folder keeps them accessible but organized."
        ),
        "query": """
            SELECT fr.id, fr.file_size
            FROM file_records fr
            JOIN file_classifications fc ON fc.file_id = fr.id
            WHERE fr.user_id = :uid
              AND fc.category = 'receipt'
              AND fr.is_deleted = FALSE
            ORDER BY fr.last_modified DESC
            LIMIT 500
        """,
    },
    {
        "type": "large_unused_files",
        "risk": "medium",
        "action": "review",
        "action_label": "Review Large Files",
        "title_fn": lambda n, b: f"{n} large files not used in a year",
        "desc_fn": lambda n, b: (
            f"These {n} files are over 100MB and haven't been modified in over a year, "
            f"consuming {_fmt(b)} of storage. Review and archive or delete what you don't need."
        ),
        "query": """
            SELECT id, file_size
            FROM file_records
            WHERE user_id = :uid
              AND file_size > 104857600
              AND last_modified < NOW() - INTERVAL '1 year'
              AND is_deleted = FALSE
            ORDER BY file_size DESC
            LIMIT 200
        """,
    },
    {
        "type": "duplicate_videos",
        "risk": "low",
        "action": "delete",
        "action_label": "Remove Video Duplicates",
        "title_fn": lambda n, b: f"{n} duplicate video files",
        "desc_fn": lambda n, b: (
            f"Found {n} video files with identical content ({_fmt(b)} wasted). "
            f"Videos are large — removing duplicates saves the most space."
        ),
        "query": """
            SELECT id, file_size
            FROM file_records
            WHERE user_id = :uid
              AND mime_type LIKE 'video/%'
              AND md5_hash IN (
                  SELECT md5_hash FROM file_records
                  WHERE user_id = :uid AND mime_type LIKE 'video/%'
                    AND is_deleted = FALSE AND md5_hash IS NOT NULL
                  GROUP BY md5_hash HAVING COUNT(*) > 1
              )
              AND is_deleted = FALSE
            ORDER BY file_size DESC
            LIMIT 200
        """,
    },
    {
        "type": "old_downloads",
        "risk": "medium",
        "action": "delete",
        "action_label": "Clear Old Downloads",
        "title_fn": lambda n, b: f"{n} old files in Downloads",
        "desc_fn": lambda n, b: (
            f"Found {n} files in your Downloads folder older than 1 year ({_fmt(b)}). "
            f"Downloads accumulate quickly and are rarely revisited."
        ),
        "query": """
            SELECT id, file_size
            FROM file_records
            WHERE user_id = :uid
              AND (file_path ILIKE '%/downloads/%' OR file_path ILIKE '%\\downloads\\%')
              AND last_modified < NOW() - INTERVAL '1 year'
              AND is_deleted = FALSE
            ORDER BY file_size DESC
            LIMIT 500
        """,
    },
    {
        "type": "tiny_files",
        "risk": "low",
        "action": "delete",
        "action_label": "Delete Empty/Tiny Files",
        "title_fn": lambda n, b: f"{n} empty or nearly-empty files",
        "desc_fn": lambda n, b: (
            f"Found {n} files under 1KB — often leftover temp files, empty documents, "
            f"or corrupt downloads. Safe to clean up."
        ),
        "query": """
            SELECT id, file_size
            FROM file_records
            WHERE user_id = :uid
              AND file_size < 1024
              AND is_deleted = FALSE
            ORDER BY indexed_at ASC
            LIMIT 1000
        """,
    },
]


# ── Engine ────────────────────────────────────────────────────────────────

async def generate_suggestions(
    db: AsyncSession,
    user_id: str,
    replace_existing: bool = True,
) -> list[Suggestion]:
    """
    Run all rules against the user's file index and persist suggestions.
    Called after every scan + classify cycle.
    """
    if replace_existing:
        # Delete old undismissed, unapplied suggestions
        old = await db.execute(
            select(Suggestion).where(
                Suggestion.user_id == user_id,
                Suggestion.dismissed == False,
                Suggestion.applied == False,
            )
        )
        for s in old.scalars().all():
            await db.delete(s)

    suggestions: list[Suggestion] = []

    for rule in RULES:
        rows = await db.execute(
            text(rule["query"]),
            {"uid": user_id},
        )
        rows_data = list(rows.mappings())

        if not rows_data:
            continue

        n = len(rows_data)
        total_bytes = sum(r["file_size"] for r in rows_data)
        file_ids = [str(r["id"]) for r in rows_data]

        s = Suggestion(
            id=str(uuid.uuid4()),
            user_id=user_id,
            suggestion_type=rule["type"],
            title=rule["title_fn"](n, total_bytes),
            description=rule["desc_fn"](n, total_bytes),
            file_ids=file_ids,
            bytes_savings=total_bytes,
            risk_level=rule["risk"],
            action=rule["action"],
            action_label=rule["action_label"],
        )
        db.add(s)
        suggestions.append(s)

    await db.flush()

    # Sort: low risk first, then by bytes_savings desc
    suggestions.sort(
        key=lambda s: (
            {"low": 0, "medium": 1, "high": 2}[s.risk_level],
            -s.bytes_savings,
        )
    )
    return suggestions


async def apply_suggestion(
    db: AsyncSession,
    suggestion_id: str,
    user_id: str,
) -> dict:
    """
    Apply a suggestion: soft-delete all files in it.
    Returns bytes freed.
    """
    from app.models.file import CleanupAction

    result = await db.execute(
        select(Suggestion).where(
            Suggestion.id == suggestion_id,
            Suggestion.user_id == user_id,
            Suggestion.applied == False,
            Suggestion.dismissed == False,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        return {"error": "Suggestion not found or already applied"}

    # Fetch files
    files = await db.execute(
        select(FileRecord).where(
            FileRecord.id.in_(suggestion.file_ids),
            FileRecord.user_id == user_id,
            FileRecord.is_deleted == False,
        )
    )
    files_list = files.scalars().all()

    bytes_freed = 0
    for f in files_list:
        f.is_deleted = True
        bytes_freed += f.file_size
        action = CleanupAction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            file_id=f.id,
            action=suggestion.action,
            action_by="suggestion",
            bytes_freed=f.file_size,
            undo_data={
                "suggestion_id": suggestion_id,
                "suggestion_type": suggestion.suggestion_type,
                "file_path": f.file_path,
                "remote_id": f.remote_id,
            },
        )
        db.add(action)

    suggestion.applied = True
    suggestion.applied_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "files_deleted": len(files_list),
        "bytes_freed": bytes_freed,
        "suggestion_id": suggestion_id,
    }


def _fmt(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b:.1f} TB"
