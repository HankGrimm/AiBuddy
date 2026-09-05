from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from ..models.match import MatchStatus, ConsentState


class MatchRequest(BaseModel):
    target_persona_id: UUID
    room_id: Optional[UUID] = None
    intro_message: Optional[str] = Field(None, max_length=500)
    stake_id: Optional[UUID] = None


class MatchResponse(BaseModel):
    id: UUID
    room_id: Optional[UUID]
    requester_persona_id: UUID
    target_persona_id: UUID
    stake_id: Optional[UUID]
    status: MatchStatus
    consent_state: ConsentState
    compatibility_score: Optional[float]
    expires_at: Optional[datetime]
    created_at: datetime
    responded_at: Optional[datetime]

    class Config:
        from_attributes = True


class MatchList(BaseModel):
    matches: List[MatchResponse]
    total: int
