from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    SECRET_KEY: str
    ENCRYPTION_KEY: str

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OAuth - Google Drive
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # OAuth - Dropbox
    DROPBOX_APP_KEY: Optional[str] = None
    DROPBOX_APP_SECRET: Optional[str] = None

    # OAuth - OneDrive (Month 3)
    ONEDRIVE_CLIENT_ID: Optional[str] = None
    ONEDRIVE_CLIENT_SECRET: Optional[str] = None
    ONEDRIVE_TENANT_ID: str = "common"

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRO_MONTHLY_PRICE_ID: Optional[str] = None
    STRIPE_PRO_YEARLY_PRICE_ID: Optional[str] = None

    # Email
    RESEND_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "noreply@declutter.app"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Thumbnail storage (Cloudflare R2 / AWS S3)
    R2_ENDPOINT: Optional[str] = None
    R2_ACCESS_KEY: Optional[str] = None
    R2_SECRET_KEY: Optional[str] = None
    R2_BUCKET: str = "declutter-thumbnails"
    THUMBNAIL_BASE_URL: Optional[str] = None

    # pHash similarity threshold (Hamming distance 0-64)
    PHASH_SIMILARITY_THRESHOLD: int = 10

    # Month 3: AI Classification
    OPENAI_API_KEY: Optional[str] = None
    # Blur threshold: images with Laplacian variance below this are "blurry"
    BLUR_THRESHOLD: float = 100.0
    # Max file size to download for AI analysis (bytes) - default 5MB
    AI_MAX_FILE_BYTES: int = 5_000_000

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
