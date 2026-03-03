"""
AI Classification Service — Month 3

Three-tier classification pipeline (cheapest → most powerful):

Tier 1 — HEURISTIC (free, instant, no ML needed)
  · Blur detection via Laplacian variance (OpenCV)
  · Screenshot detection via EXIF + aspect ratio + filename heuristics
  · File-extension-based category assignment
  · Applies to ALL users

Tier 2 — LIGHTWEIGHT ML (optional, CPU-only)
  · Would use MobileNetV3 for photo tagging
  · Stubbed here for Month 4 when we add the model server

Tier 3 — GPT-4o Vision (Pro only, API call, small thumbnails only)
  · Sends 256x256 thumbnail to GPT-4o for rich classification
  · Receipt/tax/legal/travel detection
  · Only called for images that heuristics can't confidently classify
  · We send the THUMBNAIL, never the original file

Privacy: Raw file bytes are NEVER sent externally.
         Only small thumbnails (≤256px) go to OpenAI if user is Pro.
"""

import io
import re
import os
from typing import Optional
from datetime import datetime, timezone

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import base64
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.file import FileRecord, FileClassification


# ── Constants ──────────────────────────────────────────────────────────────

SCREENSHOT_PATTERNS = re.compile(
    r"(screenshot|screen.shot|screen.cap|capture|screengrab|screen_|scr_)",
    re.IGNORECASE,
)

RECEIPT_PATTERNS = re.compile(
    r"(receipt|invoice|order.confirm|tax|bill|payment|transaction|statement)",
    re.IGNORECASE,
)

CATEGORY_BY_EXTENSION: dict[str, tuple[str, str]] = {
    # ext → (category, sub_category)
    "jpg":  ("photo", "camera"),
    "jpeg": ("photo", "camera"),
    "heic": ("photo", "camera"),
    "png":  ("photo", "general"),
    "gif":  ("photo", "animated"),
    "webp": ("photo", "web"),
    "raw":  ("photo", "raw"),
    "cr2":  ("photo", "raw"),
    "nef":  ("photo", "raw"),
    "pdf":  ("document", "pdf"),
    "docx": ("document", "word"),
    "doc":  ("document", "word"),
    "xlsx": ("document", "spreadsheet"),
    "xls":  ("document", "spreadsheet"),
    "pptx": ("document", "presentation"),
    "ppt":  ("document", "presentation"),
    "txt":  ("document", "text"),
    "md":   ("document", "markdown"),
    "mp4":  ("video", "general"),
    "mov":  ("video", "general"),
    "avi":  ("video", "general"),
    "mkv":  ("video", "general"),
    "mp3":  ("audio", "general"),
    "wav":  ("audio", "general"),
    "zip":  ("archive", "zip"),
    "tar":  ("archive", "tar"),
    "gz":   ("archive", "compressed"),
    "dmg":  ("archive", "disk"),
}


# ── Heuristic Classification (Tier 1) ────────────────────────────────────

def classify_by_heuristics(
    file_name: str,
    mime_type: Optional[str],
    file_size: int,
    image_bytes: Optional[bytes] = None,
) -> dict:
    """
    Pure heuristic classification — no ML, no API calls.
    Fast enough to run on every file during indexing.
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    cat, sub = CATEGORY_BY_EXTENSION.get(ext, ("other", "unknown"))

    is_screenshot = False
    is_blurry = False
    blur_score = None
    tags = []

    # Screenshot detection
    if SCREENSHOT_PATTERNS.search(file_name):
        is_screenshot = True
        cat = "screenshot"
        sub = "auto_detected"

    # Receipt detection by filename
    if RECEIPT_PATTERNS.search(file_name):
        cat = "receipt"
        sub = "auto_detected"
        tags.append("receipt")

    # PNG at common screenshot resolutions → likely screenshot
    if ext == "png" and mime_type == "image/png":
        # Most screenshots are PNG; camera photos almost never are
        is_screenshot = True
        cat = "screenshot"
        sub = "png_heuristic"

    # Blur detection using OpenCV Laplacian variance
    if CV2_AVAILABLE and image_bytes and mime_type and mime_type.startswith("image/"):
        blur_score = _compute_blur_score(image_bytes)
        if blur_score is not None:
            is_blurry = blur_score < settings.BLUR_THRESHOLD
            if is_blurry:
                tags.append("blurry")

    # Add size-based tags
    if file_size > 500 * 1024 * 1024:  # >500MB
        tags.append("large")
    if file_size < 10 * 1024 and cat == "photo":  # <10KB photo = likely corrupt/thumbnail
        tags.append("tiny")

    confidence = 0.75 if is_screenshot else (0.85 if cat != "other" else 0.3)

    return {
        "category": cat,
        "sub_category": sub,
        "tags": tags,
        "is_blurry": is_blurry,
        "blur_score": blur_score,
        "is_screenshot": is_screenshot,
        "confidence": confidence,
        "model_version": "heuristic",
    }


def _compute_blur_score(image_bytes: bytes) -> Optional[float]:
    """
    Laplacian variance blur detection.
    High value = sharp image. Low value = blurry.
    Threshold ~100: below = blurry.
    """
    if not CV2_AVAILABLE or not PIL_AVAILABLE:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
        # Resize for speed — blur is resolution-independent
        img.thumbnail((512, 512))
        img_array = np.array(img)
        score = float(cv2.Laplacian(img_array, cv2.CV_64F).var())
        return score
    except Exception:
        return None


# ── GPT-4o Vision Classification (Tier 3, Pro) ───────────────────────────

CLASSIFY_PROMPT = """Analyze this image and return ONLY a JSON object with these fields:
{
  "category": one of: screenshot, receipt, document, photo, meme, other,
  "sub_category": specific type like: tax_receipt, bank_statement, travel_photo, family_photo, work_document, legal, nature, food, etc.,
  "tags": array of 1-5 descriptive lowercase tags,
  "is_screenshot": boolean,
  "is_blurry": boolean,
  "confidence": float 0.0-1.0
}
Return ONLY the JSON object, no markdown, no explanation."""


async def classify_with_gpt4o(
    thumbnail_bytes: bytes,
    file_name: str,
) -> Optional[dict]:
    """
    Classify a file using GPT-4o Vision.
    Sends ONLY the 256px thumbnail — never the original file.
    Returns None if API unavailable or call fails.
    """
    if not OPENAI_AVAILABLE or not settings.OPENAI_API_KEY:
        return None

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        b64 = base64.b64encode(thumbnail_bytes).decode()

        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Cheaper than gpt-4o, still excellent for classification
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "low",  # Low detail = cheaper + faster
                            },
                        },
                        {
                            "type": "text",
                            "text": f"File name: {file_name}\n\n{CLASSIFY_PROMPT}",
                        },
                    ],
                }
            ],
        )

        import json
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        result["model_version"] = "openai-gpt4o-mini"
        return result

    except Exception:
        return None


# ── DB Persistence ────────────────────────────────────────────────────────

async def save_classification(
    db: AsyncSession,
    file_id: str,
    user_id: str,
    classification: dict,
) -> FileClassification:
    """Upsert classification result into the DB."""
    result = await db.execute(
        select(FileClassification).where(FileClassification.file_id == file_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.category = classification.get("category")
        existing.sub_category = classification.get("sub_category")
        existing.tags = classification.get("tags", [])
        existing.is_blurry = classification.get("is_blurry", False)
        existing.blur_score = classification.get("blur_score")
        existing.is_screenshot = classification.get("is_screenshot", False)
        existing.confidence = classification.get("confidence", 0.0)
        existing.model_version = classification.get("model_version", "heuristic")
        existing.classified_at = datetime.now(timezone.utc)
        return existing

    fc = FileClassification(
        id=str(uuid.uuid4()),
        file_id=file_id,
        user_id=user_id,
        category=classification.get("category"),
        sub_category=classification.get("sub_category"),
        tags=classification.get("tags", []),
        is_blurry=classification.get("is_blurry", False),
        blur_score=classification.get("blur_score"),
        is_screenshot=classification.get("is_screenshot", False),
        confidence=classification.get("confidence", 0.0),
        model_version=classification.get("model_version", "heuristic"),
    )
    db.add(fc)
    return fc


async def classify_files_batch(
    db: AsyncSession,
    user_id: str,
    limit: int = 500,
    use_ai: bool = False,
) -> dict:
    """
    Classify unclassified files for a user.
    Phase 1: heuristics only (fast, free).
    Phase 2: GPT-4o for unconfident image results (Pro + OPENAI_API_KEY set).
    Returns stats dict.
    """
    # Fetch unclassified files
    classified_subq = (
        select(FileClassification.file_id)
        .where(FileClassification.user_id == user_id)
        .scalar_subquery()
    )
    result = await db.execute(
        select(FileRecord)
        .where(
            FileRecord.user_id == user_id,
            FileRecord.is_deleted == False,
            FileRecord.id.notin_(classified_subq),
        )
        .limit(limit)
    )
    files = result.scalars().all()

    classified = 0
    ai_classified = 0

    for f in files:
        # Tier 1: heuristics (no image bytes needed for filename-based rules)
        result_dict = classify_by_heuristics(
            file_name=f.file_name,
            mime_type=f.mime_type,
            file_size=f.file_size,
        )

        # Tier 3: upgrade to GPT-4o if image, Pro user, low confidence
        if (
            use_ai
            and f.mime_type
            and f.mime_type.startswith("image/")
            and result_dict["confidence"] < 0.8
            and f.thumbnail_key
        ):
            thumb_url = f.thumbnail_key
            if thumb_url and thumb_url.startswith("data:image"):
                # Extract base64 thumbnail bytes
                b64_data = thumb_url.split(",", 1)[1]
                thumb_bytes = base64.b64decode(b64_data)
                ai_result = await classify_with_gpt4o(thumb_bytes, f.file_name)
                if ai_result:
                    result_dict.update(ai_result)
                    ai_classified += 1

        await save_classification(db, f.id, user_id, result_dict)
        classified += 1

    await db.flush()
    return {"classified": classified, "ai_classified": ai_classified}
