from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from ..models.report import ReportType, ReportStatus


class ReportCreate(BaseModel):
    reported_user_id: UUID
    report_type: ReportType
    description: str = Field(..., min_length=20, max_length=2000)
    evidence_urls: Optional[List[str]] = None


class ReportResponse(BaseModel):
    id: UUID
    reporter_id: Optional[UUID]
    reported_user_id: UUID
    report_type: ReportType
    status: ReportStatus
    is_repeat_offender: bool
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportResolve(BaseModel):
    resolution_notes: str = Field(..., min_length=10)
    action_taken: str  # "warned", "suspended", "banned", "dismissed"


class BlockCreate(BaseModel):
    blocked_user_id: UUID


class BlockResponse(BaseModel):
    id: UUID
    blocker_id: UUID
    blocked_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
