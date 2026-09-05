"""
Transfer model — MON gifting between users.
Refs #16
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class TransferStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Transfer(Base):
    __tablename__ = "sm_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sm_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sm_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_mon = Column(Numeric(precision=18, scale=9), nullable=False)
    tx_hash = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(
        SAEnum(TransferStatus),
        default=TransferStatus.PENDING,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
