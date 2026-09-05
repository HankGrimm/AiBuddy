from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE_UNLOCK = "image_unlock"
    MEETUP_REQUEST = "meetup_request"
    SYSTEM = "system"


class Message(Base):
    __tablename__ = "sm_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("sm_matches.id", ondelete="CASCADE"), nullable=False)
    sender_persona_id = Column(UUID(as_uuid=True), ForeignKey("sm_personas.id", ondelete="SET NULL"), nullable=True)
    type = Column(SAEnum(MessageType, values_callable=lambda x: [e.value for e in x]), default=MessageType.TEXT, nullable=False)
    content = Column(Text, nullable=False)
    is_encrypted = Column(Boolean, default=True, nullable=False)
    stake_id = Column(UUID(as_uuid=True), ForeignKey("sm_stakes.id", ondelete="SET NULL"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    match = relationship("Match", back_populates="messages")
    sender_persona = relationship("Persona", foreign_keys=[sender_persona_id])
