from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class VerificationLevel(str, enum.Enum):
    NONE = "none"
    WALLET = "wallet"
    PHONE = "phone"
    ID = "id"
    FULL = "full"


class PrivacyMode(str, enum.Enum):
    PUBLIC = "public"
    SEMI_PRIVATE = "semi_private"
    PRIVATE = "private"


class User(Base):
    __tablename__ = "sm_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_address = Column(String, unique=True, nullable=False, index=True)
    did = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    age_verified = Column(Boolean, default=False, nullable=False)
    verification_level = Column(
        SAEnum(VerificationLevel), default=VerificationLevel.WALLET, nullable=False
    )
    privacy_mode = Column(
        SAEnum(PrivacyMode), default=PrivacyMode.SEMI_PRIVATE, nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    personas = relationship("Persona", back_populates="user", cascade="all, delete-orphan")
    stakes = relationship("Stake", foreign_keys="Stake.user_id", back_populates="user", cascade="all, delete-orphan")
    reports_filed = relationship("Report", foreign_keys="Report.reporter_id", back_populates="reporter")
    blocks = relationship("Block", foreign_keys="Block.blocker_id", back_populates="blocker")
