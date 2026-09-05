"""
Moment NFT model — commemorates a confirmed meetup attestation as an on-chain NFT.
Refs #17
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class MomentNFTStatus(str, enum.Enum):
    PENDING = "pending"
    MINTED = "minted"
    FAILED = "failed"


class MomentNFT(Base):
    __tablename__ = "sm_moment_nfts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sm_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attestation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sm_meetup_attestations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    mint_address = Column(String, nullable=True)  # Monad NFT address
    metadata_uri = Column(String, nullable=True)  # off-chain metadata URI
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        SAEnum(MomentNFTStatus),
        default=MomentNFTStatus.PENDING,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
