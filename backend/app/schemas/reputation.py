from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from ..models.reputation import ReputationEventType


class ReputationResponse(BaseModel):
    user_id: UUID
    reliability_score: float
    safety_score: float
    response_score: float
    meetup_completion_score: float
    no_show_rate: float
    consent_confirmation_score: float
    composite_score: float
    total_meetups: int
    total_messages: int
    reports_received: int
    stakes_slashed: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    target_user_id: UUID
    reference_id: UUID  # match_id or attestation_id
    event_type: ReputationEventType
    notes: Optional[str] = Field(None, max_length=500)
