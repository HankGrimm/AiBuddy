from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from ..models.escrow import EscrowType, EscrowStatus


class EscrowCreate(BaseModel):
    type: EscrowType
    counterparty_user_id: UUID
    amount_usdc: float = Field(..., gt=0)
    confirm_deadline: Optional[datetime] = None


class EscrowResponse(BaseModel):
    id: UUID
    type: EscrowType
    initiator_user_id: Optional[UUID]
    counterparty_user_id: Optional[UUID]
    amount_usdc: float
    status: EscrowStatus
    hcs_topic_id: Optional[str]
    confirm_deadline: Optional[datetime]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class EscrowDispute(BaseModel):
    reason: str = Field(..., min_length=20)
