from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    tier: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StorageConnectionResponse(BaseModel):
    id: str
    provider: str
    account_email: Optional[str]
    total_bytes: Optional[int]
    used_bytes: Optional[int]
    last_synced: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanJobResponse(BaseModel):
    id: str
    status: str
    scan_type: str
    files_scanned: int
    files_total: Optional[int]
    bytes_reclaimable: int
    progress_pct: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class FileRecordResponse(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_size: int
    mime_type: Optional[str]
    md5_hash: Optional[str]
    last_modified: Optional[datetime]
    is_deleted: bool
    thumbnail_key: Optional[str]

    model_config = {"from_attributes": True}


class DuplicateGroupResponse(BaseModel):
    id: str
    match_type: str
    similarity: float
    total_wasted_bytes: int
    resolved: bool
    file_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    total_files: int
    total_size_bytes: int
    potential_savings_bytes: int
    low_risk_bytes: int
    review_needed_bytes: int
    duplicate_groups: int
    last_scan: Optional[datetime]
    storage_connections: int
