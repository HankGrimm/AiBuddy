from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class StakeType(str, enum.Enum):
    DM = "dm"
    UNLOCK_PHOTO = "unlock_photo"
    JOIN_ROOM = "join_room"
    REQUEST_MEETUP = "request_meetup"
    CONFIRM_MEETUP = "confirm_meetup"


class StakeStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REFUNDED = "refunded"
    SLASHED = "slashed"
    RELEASED = "released"
    DISPUTED = "disputed"


class Stake(Base):
    __tablename__ = "sm_stakes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(UUID(as_uuid=True), ForeignKey("sm_rooms.id", ondelete="SET NULL"), nullable=True)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    stake_type = Column(SAEnum(StakeType), nullable=False)
    status = Column(SAEnum(StakeStatus), default=StakeStatus.PENDING, nullable=False)
    amount_usdc = Column(Float, nullable=False)
    currency = Column(String(10), default="USDC", nullable=False)
    tx_hash = Column(String, nullable=True)
    escrow_id = Column(UUID(as_uuid=True), ForeignKey("sm_escrows.id", ondelete="SET NULL"), nullable=True)
    slash_reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="stakes")
    room = relationship("Room", back_populates="stakes")
    escrow = relationship("Escrow", back_populates="stakes")
