from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class ReportType(str, enum.Enum):
    HARASSMENT = "harassment"
    SPAM = "spam"
    CATFISHING = "catfishing"
    SCAM_ATTEMPT = "scam_attempt"
    UNDERAGE_USER = "underage_user"
    NO_SHOW_ABUSE = "no_show_abuse"
    FALSE_REPORTING = "false_reporting"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Report(Base):
    __tablename__ = "sm_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    reported_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(SAEnum(ReportType), nullable=False)
    description = Column(Text, nullable=False)
    evidence_urls = Column(Text, nullable=True)  # JSON list of URLs
    status = Column(SAEnum(ReportStatus), default=ReportStatus.PENDING, nullable=False)
    resolution_notes = Column(Text, nullable=True)
    is_repeat_offender = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reports_filed")
