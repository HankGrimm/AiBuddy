from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class EscrowStatus(str, enum.Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    RESOLVED = "resolved"
    REFUNDED = "refunded"
    SLASHED = "slashed"


class EscrowType(str, enum.Enum):
    MEETUP = "meetup"
    DM_UNLOCK = "dm_unlock"
    ROOM_JOIN = "room_join"


class Escrow(Base):
    __tablename__ = "sm_escrows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(SAEnum(EscrowType), nullable=False)
    initiator_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    counterparty_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    amount_usdc = Column(Float, nullable=False)
    status = Column(SAEnum(EscrowStatus), default=EscrowStatus.OPEN, nullable=False)
    hcs_topic_id = Column(String, nullable=True)  # Hedera anchoring
    dispute_reason = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    confirm_deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    stakes = relationship("Stake", back_populates="escrow")
