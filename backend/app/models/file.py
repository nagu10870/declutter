import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, BigInteger, Boolean, DateTime, Float,
    Text, ForeignKey, JSON, Integer, ARRAY
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class StorageConnection(Base):
    __tablename__ = "storage_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google_drive, dropbox, local
    oauth_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="storage_connections")
    scan_jobs: Mapped[list["ScanJob"]] = relationship(back_populates="connection", cascade="all, delete-orphan")
    file_records: Mapped[list["FileRecord"]] = relationship(back_populates="connection", cascade="all, delete-orphan")


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("storage_connections.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, running, completed, failed
    scan_type: Mapped[str] = mapped_column(String(30), default="full")  # full, incremental, duplicates_only
    files_scanned: Mapped[int] = mapped_column(Integer, default=0)
    files_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_reclaimable: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="scan_jobs")
    connection: Mapped["StorageConnection"] = relationship(back_populates="scan_jobs")

    @property
    def progress_pct(self) -> float:
        if not self.files_total or self.files_total == 0:
            return 0.0
        return min(100.0, (self.files_scanned / self.files_total) * 100)


class FileRecord(Base):
    __tablename__ = "file_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("storage_connections.id", ondelete="CASCADE"), nullable=False)
    remote_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    md5_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="file_records")
    connection: Mapped["StorageConnection"] = relationship(back_populates="file_records")


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)  # exact, similar, fuzzy
    similarity: Mapped[float] = mapped_column(Float, default=1.0)
    total_wasted_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CleanupAction(Base):
    __tablename__ = "cleanup_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("file_records.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # delete, move, archive, keep
    action_by: Mapped[str] = mapped_column(String(20), default="user")  # user, auto
    bytes_freed: Mapped[int] = mapped_column(BigInteger, default=0)
    undo_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="cleanup_actions")


# ── Month 3 Models ─────────────────────────────────────────────────────────

class FileClassification(Base):
    """AI-generated classification tags for a file."""
    __tablename__ = "file_classifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Primary category: screenshot, receipt, document, photo, video, archive, other
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Sub-category: tax, legal, work, personal, travel, family, nature, etc.
    sub_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Tags array stored as JSON
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Quality signals
    is_blurry: Mapped[bool] = mapped_column(Boolean, default=False)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)   # Laplacian variance
    is_screenshot: Mapped[bool] = mapped_column(Boolean, default=False)

    # Confidence 0.0-1.0
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # Model used: "heuristic", "openai-gpt4o", "mobilenet"
    model_version: Mapped[str] = mapped_column(String(50), default="heuristic")

    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Suggestion(Base):
    """Smart cleanup suggestion generated by the rules engine."""
    __tablename__ = "suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Type maps to a rule: old_screenshots, blurry_photos, large_unused, receipt_archive, etc.
    suggestion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # File IDs this suggestion applies to (JSON array of strings)
    file_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    bytes_savings: Mapped[int] = mapped_column(BigInteger, default=0)

    # "low", "medium", "high"
    risk_level: Mapped[str] = mapped_column(String(10), default="low")
    # Recommended action: delete, archive, move
    action: Mapped[str] = mapped_column(String(20), default="delete")
    action_label: Mapped[str] = mapped_column(String(50), default="Delete All")

    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Schedule(Base):
    """Automated recurring cleanup schedule."""
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # weekly_scan, monthly_dedupe, auto_delete_trash
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Human label
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # cron expression, e.g. "0 2 * * 1" = every Monday at 2am
    cron_expr: Mapped[str] = mapped_column(String(50), nullable=False)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
