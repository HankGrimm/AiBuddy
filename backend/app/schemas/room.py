from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from ..models.room import RoomType, RoomPrivacyLevel
from ..models.persona import IntentMode


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=128)
    description: Optional[str] = Field(None, max_length=1000)
    type: RoomType = RoomType.LOUNGE
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_radius_meters: Optional[float] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    privacy_level: RoomPrivacyLevel = RoomPrivacyLevel.PUBLIC
    stake_required: float = Field(default=0.0, ge=0)
    intent_modes: List[IntentMode] = []
    max_members: Optional[int] = None


class RoomResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    type: RoomType
    host_user_id: Optional[UUID]
    location: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    privacy_level: RoomPrivacyLevel
    stake_required: float
    intent_modes: List[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoomJoin(BaseModel):
    persona_id: UUID
    stake_tx_hash: Optional[str] = None  # Required if room has stake_required > 0
