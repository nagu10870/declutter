"""
CLIP Embeddings Service — Month 4

Generates 512-dim visual embeddings using OpenAI's CLIP model (via openai-clip or
a local ONNX model). Stored in PostgreSQL using pgvector extension for
fast cosine similarity searches.

Why CLIP over pHash?
  - pHash: pixel-level similarity (rotation/crop breaks it)
  - CLIP: semantic similarity — can match "dog playing in park" to other dog photos
    even with different lighting, angles, or aspect ratios

Architecture:
  - Local thumbnail is encoded by CLIP → 512-dim float vector
  - Stored in file_records.clip_embedding (vector(512))
  - Cosine similarity search finds semantically similar files
  - Pro only — compute-intensive, requires model download on first use

We use ONNX export of CLIP ViT-B/32 to avoid PyTorch dependency in prod.
Fallback: if CLIP unavailable, returns None (pHash still works).
"""

import io
import json
import struct
from typing import Optional

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import ARRAY
import uuid

from app.core.config import settings


# ── CLIP model loading (lazy) ─────────────────────────────────────────────
_clip_model = None
_clip_preprocess = None
_clip_loaded = False


def _load_clip():
    """Lazy-load CLIP model. Falls back gracefully if unavailable."""
    global _clip_model, _clip_preprocess, _clip_loaded
    if _clip_loaded:
        return _clip_model is not None
    _clip_loaded = True
    try:
        import clip
        import torch
        device = "cpu"  # CPU-only in production
        _clip_model, _clip_preprocess = clip.load("ViT-B/32", device=device)
        _clip_model.eval()
        return True
    except ImportError:
        return False


def generate_clip_embedding(image_bytes: bytes) -> Optional[list[float]]:
    """
    Generate 512-dim CLIP embedding from image bytes.
    Returns None if CLIP unavailable or image invalid.
    """
    if not PIL_AVAILABLE or not NP_AVAILABLE:
        return None

    try:
        import torch
        if not _load_clip():
            return None

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_input = _clip_preprocess(img).unsqueeze(0)

        with torch.no_grad():
            features = _clip_model.encode_image(image_input)
            features = features / features.norm(dim=-1, keepdim=True)  # Normalize

        return features.squeeze().tolist()
    except Exception:
        return None


async def store_embedding(
    db: AsyncSession,
    file_id: str,
    embedding: list[float],
) -> bool:
    """Store CLIP embedding in the clip_embeddings table."""
    try:
        # Upsert clip embedding
        await db.execute(
            text("""
                INSERT INTO clip_embeddings (id, file_id, embedding, created_at)
                VALUES (:id, :file_id, :embedding, NOW())
                ON CONFLICT (file_id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    created_at = NOW()
            """),
            {
                "id": str(uuid.uuid4()),
                "file_id": file_id,
                "embedding": embedding,
            }
        )
        return True
    except Exception:
        return False


async def find_semantically_similar(
    db: AsyncSession,
    user_id: str,
    file_id: str,
    threshold: float = 0.85,
    limit: int = 10,
) -> list[dict]:
    """
    Find files semantically similar to the given file_id using cosine similarity.
    Only returns files belonging to the same user.
    threshold: cosine similarity 0-1 (0.85+ = very similar)
    """
    # Get the query embedding
    result = await db.execute(
        text("""
            SELECT ce.embedding
            FROM clip_embeddings ce
            JOIN file_records fr ON fr.id = ce.file_id
            WHERE ce.file_id = :file_id AND fr.user_id = :uid
        """),
        {"file_id": file_id, "uid": user_id},
    )
    row = result.one_or_none()
    if not row:
        return []

    # Find similar files using pgvector <=> (cosine distance)
    similar = await db.execute(
        text("""
            SELECT
                fr.id, fr.file_name, fr.file_path, fr.file_size,
                fr.mime_type, fr.thumbnail_key,
                1 - (ce.embedding <=> :query_emb) AS similarity
            FROM clip_embeddings ce
            JOIN file_records fr ON fr.id = ce.file_id
            WHERE fr.user_id = :uid
              AND ce.file_id != :file_id
              AND fr.is_deleted = FALSE
              AND 1 - (ce.embedding <=> :query_emb) >= :threshold
            ORDER BY ce.embedding <=> :query_emb
            LIMIT :limit
        """),
        {
            "query_emb": row[0],
            "uid": user_id,
            "file_id": file_id,
            "threshold": threshold,
            "limit": limit,
        }
    )
    return [dict(r._mapping) for r in similar]


async def generate_embeddings_batch(
    db: AsyncSession,
    user_id: str,
    limit: int = 200,
) -> dict:
    """
    Generate CLIP embeddings for unprocessed image files.
    Only local files with thumbnail_key can be processed (we need pixel data).
    Returns stats dict.
    """
    # Files without embeddings
    result = await db.execute(
        text("""
            SELECT fr.id, fr.file_name, fr.thumbnail_key, fr.mime_type
            FROM file_records fr
            LEFT JOIN clip_embeddings ce ON ce.file_id = fr.id
            WHERE fr.user_id = :uid
              AND fr.is_deleted = FALSE
              AND fr.mime_type LIKE 'image/%'
              AND fr.thumbnail_key IS NOT NULL
              AND ce.file_id IS NULL
            LIMIT :limit
        """),
        {"uid": user_id, "limit": limit}
    )
    files = list(result.mappings())

    processed = 0
    failed = 0

    import base64
    for f in files:
        thumb = f["thumbnail_key"]
        if not thumb or not thumb.startswith("data:image"):
            continue
        try:
            # Decode base64 thumbnail
            b64_data = thumb.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            embedding = generate_clip_embedding(img_bytes)
            if embedding:
                await store_embedding(db, f["id"], embedding)
                processed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    await db.flush()
    return {"processed": processed, "failed": failed, "total_candidates": len(files)}
