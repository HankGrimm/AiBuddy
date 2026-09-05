from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Float, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class ReputationEventType(str, enum.Enum):
    MEETUP_COMPLETED = "meetup_completed"
    MEETUP_NO_SHOW = "meetup_no_show"
    MESSAGE_RESPONDED = "message_responded"
    MESSAGE_IGNORED = "message_ignored"
    MATCH_ACCEPTED = "match_accepted"
    MATCH_REJECTED = "match_rejected"
    REPORT_RECEIVED = "report_received"
    REPORT_RESOLVED = "report_resolved"
    STAKE_SLASHED = "stake_slashed"
    CONSENT_CONFIRMED = "consent_confirmed"
    POSITIVE_FEEDBACK = "positive_feedback"
    NEGATIVE_FEEDBACK = "negative_feedback"


class ReputationScore(Base):
    __tablename__ = "sm_reputation_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="CASCADE"), nullable=False, unique=True)
    reliability_score = Column(Float, default=50.0)
    safety_score = Column(Float, default=50.0)
    response_score = Column(Float, default=50.0)
    meetup_completion_score = Column(Float, default=50.0)
    no_show_rate = Column(Float, default=0.0)
    consent_confirmation_score = Column(Float, default=50.0)
    total_meetups = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    reports_received = Column(Integer, default=0)
    stakes_slashed = Column(Integer, default=0)
    composite_score = Column(Float, default=50.0)
    last_decay_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReputationEvent(Base):
    __tablename__ = "sm_reputation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(SAEnum(ReputationEventType), nullable=False)
    delta = Column(Float, nullable=False)
    dimension = Column(String(64), nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=True)  # match_id, attestation_id, etc.
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
