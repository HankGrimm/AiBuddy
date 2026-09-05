"""
Transfer schemas — Refs #16
"""
from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from ..models.transfer import TransferStatus


class TransferCreate(BaseModel):
    recipient_wallet: str
    amount_mon: float
    message: Optional[str] = None

    @field_validator("amount_mon")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount_mon must be greater than 0")
        return v


class TransferResponse(BaseModel):
    id: UUID
    sender_id: UUID
    recipient_id: UUID
    amount_mon: float
    tx_hash: Optional[str]
    message: Optional[str]
    status: TransferStatus
    created_at: datetime

    model_config = {"from_attributes": True}
