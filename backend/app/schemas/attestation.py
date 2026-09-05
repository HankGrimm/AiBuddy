from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from ..models.attestation import AttestationMethod, AttestationStatus


class AttestationInitiate(BaseModel):
    match_id: UUID
    method: AttestationMethod
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    escrow_id: Optional[UUID] = None


class AttestationConfirm(BaseModel):
    token: Optional[str] = None  # QR/BLE/NFC token
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AttestationResponse(BaseModel):
    id: UUID
    match_id: UUID
    method: AttestationMethod
    status: AttestationStatus
    token: Optional[str]
    initiator_confirmed: bool
    counterparty_confirmed: bool
    hcs_message_id: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    confirmed_at: Optional[datetime]

    class Config:
        from_attributes = True
