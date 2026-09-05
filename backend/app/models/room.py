from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Boolean, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class RoomType(str, enum.Enum):
    EVENT = "event"
    LOUNGE = "lounge"
    CREATOR = "creator"
    TRAVEL = "travel"
    SPEED_DATING = "speed_dating"
    PRIVATE = "private"


class RoomPrivacyLevel(str, enum.Enum):
    PUBLIC = "public"
    INVITE_ONLY = "invite_only"
    STAKE_GATED = "stake_gated"
    ANONYMOUS = "anonymous"


class Room(Base):
    __tablename__ = "sm_rooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    description = Column(String(1000), nullable=True)
    type = Column(SAEnum(RoomType), default=RoomType.LOUNGE, nullable=False)
    host_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    location = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geofence_radius_meters = Column(Float, nullable=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    privacy_level = Column(SAEnum(RoomPrivacyLevel), default=RoomPrivacyLevel.PUBLIC, nullable=False)
    stake_required = Column(Float, default=0.0, nullable=False)  # USDC amount
    intent_modes = Column(JSON, default=list, nullable=False)  # list of IntentMode values
    max_members = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    personas = relationship("Persona", back_populates="room")
    stakes = relationship("Stake", back_populates="room")
