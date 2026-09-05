from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..core.database import Base


class AttestationMethod(str, enum.Enum):
    QR_CODE = "qr_code"
    BLE_PROXIMITY = "ble_proximity"
    NFC_TAP = "nfc_tap"
    GPS_CHECKIN = "gps_checkin"
    MUTUAL_CONFIRMATION = "mutual_confirmation"
    HOST_VERIFICATION = "host_verification"


class AttestationStatus(str, enum.Enum):
    INITIATED = "initiated"
    PENDING_CONFIRM = "pending_confirm"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"


class MeetupAttestation(Base):
    __tablename__ = "sm_meetup_attestations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("sm_matches.id", ondelete="CASCADE"), nullable=False)
    initiator_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    counterparty_user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="SET NULL"), nullable=True)
    method = Column(SAEnum(AttestationMethod), nullable=False)
    status = Column(SAEnum(AttestationStatus), default=AttestationStatus.INITIATED, nullable=False)
    token = Column(String, nullable=True)  # QR/BLE/NFC token
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    hcs_message_id = Column(String, nullable=True)  # Hedera HCS anchor
    initiator_confirmed = Column(Boolean, default=False)
    counterparty_confirmed = Column(Boolean, default=False)
    escrow_id = Column(UUID(as_uuid=True), ForeignKey("sm_escrows.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
