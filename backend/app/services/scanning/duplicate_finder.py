"""
Core duplicate detection engine.

Strategy:
1. Exact duplicates  → MD5 hash grouping (free, instant, O(n))
2. Similar images    → pHash + Hamming distance clustering (O(n²), MVP-safe for < 50k files)
3. Large files       → sorted file_size query
4. Old unused files  → last_modified age query
"""

import hashlib
import io
from pathlib import Path
from typing import Optional

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models.file import FileRecord, DuplicateGroup


# ── Hashing Utilities ──────────────────────────────────────────────────────

def compute_md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stream_hash_file(file_path: str | Path, chunk_size: int = 65536) -> str:
    """MD5-hash a local file without loading it fully into memory."""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def compute_phash(image_data: bytes) -> Optional[str]:
    """Perceptual hash for image similarity. Returns hex string or None."""
    if not IMAGEHASH_AVAILABLE:
        return None
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        return str(imagehash.phash(img))
    except Exception:
        return None


def phash_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two pHash hex strings."""
    if not IMAGEHASH_AVAILABLE:
        return 999
    h1 = imagehash.hex_to_hash(hash1)
    h2 = imagehash.hex_to_hash(hash2)
    return h1 - h2


def are_visually_similar(hash1: str, hash2: str, threshold: int = 10) -> bool:
    """
    Thresholds:
      0     → identical pixel data
      1-5   → near-identical (different compression, slight edit)
      6-10  → visually similar (crop, resize, filter)
      11-20 → loosely related
    """
    return phash_distance(hash1, hash2) < threshold


# ── DB-backed Duplicate Finders ────────────────────────────────────────────

async def find_exact_duplicates(
    db: AsyncSession, user_id: str
) -> list[dict]:
    """
    Return groups of files sharing the same MD5 hash.
    Excludes already-deleted files.
    """
    rows = await db.execute(
        text("""
            SELECT
                md5_hash,
                array_agg(id ORDER BY indexed_at ASC) AS file_ids,
                COUNT(*) AS file_count,
                MIN(file_size) AS smallest_size,
                SUM(file_size) AS total_size
            FROM file_records
            WHERE user_id = :user_id
              AND is_deleted = FALSE
              AND md5_hash IS NOT NULL
            GROUP BY md5_hash
            HAVING COUNT(*) > 1
            ORDER BY total_size DESC
        """),
        {"user_id": user_id},
    )
    groups = []
    for row in rows.mappings():
        wasted = row["total_size"] - row["smallest_size"]
        groups.append({
            "match_type": "exact",
            "similarity": 1.0,
            "file_ids": list(row["file_ids"]),
            "wasted_bytes": int(wasted),
        })
    return groups


async def find_similar_images(
    db: AsyncSession,
    user_id: str,
    threshold: int = 10,
) -> list[dict]:
    """
    Cluster images by perceptual hash similarity using Union-Find.
    Only runs for Pro users (caller is responsible for tier gate).
    """
    result = await db.execute(
        select(FileRecord.id, FileRecord.perceptual_hash, FileRecord.file_size)
        .where(
            FileRecord.user_id == user_id,
            FileRecord.mime_type.like("image/%"),
            FileRecord.perceptual_hash.isnot(None),
            FileRecord.is_deleted == False,
        )
    )
    rows = result.all()

    if len(rows) < 2 or not IMAGEHASH_AVAILABLE:
        return []

    # Union-Find
    parent = {r.id: r.id for r in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    # O(n²) — acceptable for < 50k images per user
    items = list(rows)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i].perceptual_hash and items[j].perceptual_hash:
                dist = phash_distance(items[i].perceptual_hash, items[j].perceptual_hash)
                if dist < threshold:
                    union(items[i].id, items[j].id)

    # Group by root
    clusters: dict[str, list] = {}
    for row in rows:
        root = find(row.id)
        clusters.setdefault(root, []).append(row)

    groups = []
    for cluster_rows in clusters.values():
        if len(cluster_rows) > 1:
            total = sum(r.file_size for r in cluster_rows)
            keep = min(r.file_size for r in cluster_rows)
            groups.append({
                "match_type": "similar",
                "similarity": 0.9,
                "file_ids": [r.id for r in cluster_rows],
                "wasted_bytes": total - keep,
            })
    return groups


async def find_large_files(
    db: AsyncSession,
    user_id: str,
    min_size_mb: int = 100,
    limit: int = 100,
) -> list[dict]:
    min_bytes = min_size_mb * 1024 * 1024
    result = await db.execute(
        select(FileRecord)
        .where(
            FileRecord.user_id == user_id,
            FileRecord.file_size >= min_bytes,
            FileRecord.is_deleted == False,
        )
        .order_by(FileRecord.file_size.desc())
        .limit(limit)
    )
    files = result.scalars().all()
    return [
        {
            "id": f.id,
            "file_name": f.file_name,
            "file_path": f.file_path,
            "file_size": f.file_size,
            "last_modified": f.last_modified,
            "mime_type": f.mime_type,
        }
        for f in files
    ]


async def find_old_unused_files(
    db: AsyncSession,
    user_id: str,
    days_old: int = 365,
    limit: int = 200,
) -> list[dict]:
    result = await db.execute(
        text("""
            SELECT id, file_name, file_path, file_size, last_modified, mime_type,
                   EXTRACT(DAY FROM NOW() - last_modified)::int AS days_old
            FROM file_records
            WHERE user_id = :user_id
              AND last_modified < NOW() - INTERVAL '1 day' * :days
              AND is_deleted = FALSE
            ORDER BY file_size DESC
            LIMIT :limit
        """),
        {"user_id": user_id, "days": days_old, "limit": limit},
    )
    return [dict(r) for r in result.mappings()]


async def persist_duplicate_groups(
    db: AsyncSession, user_id: str, groups: list[dict]
) -> list[DuplicateGroup]:
    """Save newly found duplicate groups to DB (replaces previous unresolved groups)."""
    # Clear old unresolved groups
    result = await db.execute(
        select(DuplicateGroup).where(
            DuplicateGroup.user_id == user_id,
            DuplicateGroup.resolved == False,
        )
    )
    for old in result.scalars().all():
        await db.delete(old)

    saved = []
    for g in groups:
        dg = DuplicateGroup(
            user_id=user_id,
            match_type=g["match_type"],
            similarity=g["similarity"],
            total_wasted_bytes=g["wasted_bytes"],
        )
        db.add(dg)
        saved.append(dg)

    await db.flush()
    return saved
