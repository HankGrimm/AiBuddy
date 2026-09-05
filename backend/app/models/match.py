from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class ConsentState(str, enum.Enum):
    NONE = "none"
    REQUESTED = "requested"
    GRANTED = "granted"
    REVOKED = "revoked"


class Match(Base):
    __tablename__ = "sm_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("sm_rooms.id", ondelete="SET NULL"), nullable=True)
    requester_persona_id = Column(UUID(as_uuid=True), ForeignKey("sm_personas.id", ondelete="CASCADE"), nullable=False)
    target_persona_id = Column(UUID(as_uuid=True), ForeignKey("sm_personas.id", ondelete="CASCADE"), nullable=False)
    stake_id = Column(UUID(as_uuid=True), ForeignKey("sm_stakes.id", ondelete="SET NULL"), nullable=True)
    status = Column(SAEnum(MatchStatus), default=MatchStatus.PENDING, nullable=False)
    consent_state = Column(SAEnum(ConsentState), default=ConsentState.REQUESTED, nullable=False)
    compatibility_score = Column(Float, nullable=True)
    intro_message = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)

    requester_persona = relationship("Persona", foreign_keys=[requester_persona_id], back_populates="sent_matches")
    target_persona = relationship("Persona", foreign_keys=[target_persona_id], back_populates="received_matches")
    messages = relationship("Message", back_populates="match", cascade="all, delete-orphan")
