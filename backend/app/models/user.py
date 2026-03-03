import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class UserTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Month 3
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Month 6
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    storage_connections: Mapped[list["StorageConnection"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    scan_jobs: Mapped[list["ScanJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    file_records: Mapped[list["FileRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cleanup_actions: Mapped[list["CleanupAction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_pro(self) -> bool:
        return self.tier in ("pro", "business")

    def __repr__(self):
        return f"<User {self.email} [{self.tier}]>"
