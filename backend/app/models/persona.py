from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class IntentMode(str, enum.Enum):
    SOCIAL = "social"
    DATING = "dating"
    NETWORKING = "networking"
    TRAVEL = "travel"
    CREATOR = "creator"
    ANONYMOUS = "anonymous"


class VisibilityScope(str, enum.Enum):
    ROOM_ONLY = "room_only"
    MUTUAL_MATCH = "mutual_match"
    PUBLIC = "public"


class Persona(Base):
    __tablename__ = "sm_personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(UUID(as_uuid=True), ForeignKey("sm_rooms.id", ondelete="SET NULL"), nullable=True)
    display_name = Column(String(64), nullable=False)
    avatar_url = Column(String, nullable=True)
    bio = Column(String(500), nullable=True)
    intent_mode = Column(SAEnum(IntentMode), default=IntentMode.SOCIAL, nullable=False)
    visibility_scope = Column(SAEnum(VisibilityScope), default=VisibilityScope.ROOM_ONLY, nullable=False)
    reputation_scope = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="personas")
    room = relationship("Room", back_populates="personas")
    sent_matches = relationship("Match", foreign_keys="Match.requester_persona_id", back_populates="requester_persona")
    received_matches = relationship("Match", foreign_keys="Match.target_persona_id", back_populates="target_persona")
