"""
Thumbnail Service — Month 2

Generates 256x256 JPEG thumbnails for image files.
Storage strategy:
  - If R2/S3 is configured: upload to object storage, return CDN URL
  - Otherwise: base64-encode and return as data URL (dev mode)

IMPORTANT: Raw file bytes are NEVER persisted permanently.
Thumbnails are generated on-demand from a temporary byte buffer,
then immediately discarded. Only the resized thumbnail is stored.
"""

import io
import uuid
import base64
from typing import Optional

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import boto3
    from botocore.config import Config as BotoConfig
    BOTO_AVAILABLE = True
except ImportError:
    BOTO_AVAILABLE = False

from app.core.config import settings


THUMBNAIL_SIZE = (256, 256)
THUMBNAIL_QUALITY = 75


def _get_s3_client():
    """Get boto3 S3 client configured for Cloudflare R2 or AWS S3."""
    if not BOTO_AVAILABLE or not settings.R2_ACCESS_KEY:
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def generate_thumbnail(image_bytes: bytes) -> Optional[bytes]:
    """
    Resize image to 256x256 JPEG thumbnail.
    Returns JPEG bytes or None on failure.
    """
    if not PIL_AVAILABLE:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)   # Respect EXIF orientation
        img = img.convert("RGB")
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)

        # Center-crop to exact square
        w, h = img.size
        left = (w - min(w, h)) // 2
        top = (h - min(w, h)) // 2
        img = img.crop((left, top, left + min(w, h), top + min(w, h)))
        img = img.resize(THUMBNAIL_SIZE, Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
        return out.getvalue()
    except Exception:
        return None


async def store_thumbnail(
    file_id: str,
    image_bytes: bytes,
    user_id: str,
) -> Optional[str]:
    """
    Generate thumbnail and store it.
    Returns: URL/key string, or None if failed.
    """
    thumb_bytes = generate_thumbnail(image_bytes)
    if not thumb_bytes:
        return None

    s3 = _get_s3_client()
    if s3:
        # Upload to R2/S3
        key = f"thumbs/{user_id}/{file_id}.jpg"
        try:
            s3.put_object(
                Bucket=settings.R2_BUCKET,
                Key=key,
                Body=thumb_bytes,
                ContentType="image/jpeg",
                CacheControl="public, max-age=31536000",  # 1 year
            )
            base_url = settings.THUMBNAIL_BASE_URL or f"https://{settings.R2_BUCKET}.r2.dev"
            return f"{base_url}/{key}"
        except Exception:
            pass

    # Fallback: return as base64 data URL (dev / no-storage mode)
    b64 = base64.b64encode(thumb_bytes).decode()
    return f"data:image/jpeg;base64,{b64}"


def get_thumbnail_url(thumbnail_key: Optional[str]) -> Optional[str]:
    """
    Return the public URL for a stored thumbnail.
    thumbnail_key may be:
      - A full URL (Google Drive thumbnailLink, or our CDN URL)
      - A data: URL (dev fallback)
      - A relative S3 key (legacy)
    """
    if not thumbnail_key:
        return None
    if thumbnail_key.startswith(("http://", "https://", "data:")):
        return thumbnail_key
    # Legacy relative key
    base = settings.THUMBNAIL_BASE_URL or ""
    return f"{base}/{thumbnail_key}" if base else None
