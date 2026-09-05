from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from ..models.stake import StakeType, StakeStatus


class StakeCreate(BaseModel):
    stake_type: StakeType
    amount_mon: float = Field(..., gt=0)
    room_id: Optional[UUID] = None
    target_user_id: Optional[UUID] = None
    tx_hash: Optional[str] = None


class StakeResponse(BaseModel):
    id: UUID
    user_id: UUID
    stake_type: StakeType
    status: StakeStatus
    amount_mon: float
    currency: str
    tx_hash: Optional[str]
    escrow_id: Optional[UUID]
    expires_at: Optional[datetime]
    created_at: datetime
    resolved_at: Optional[datetime]
    explorer_url: Optional[str] = None

    @model_validator(mode="after")
    def _set_explorer_url(self) -> "StakeResponse":
        if self.tx_hash:
            self.explorer_url = (
                f"https://testnet.monadexplorer.com/tx/{self.tx_hash}"
            )
        return self

    class Config:
        from_attributes = True


class StakeSlash(BaseModel):
    reason: str = Field(..., min_length=10)
