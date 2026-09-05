from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from ..models.persona import IntentMode, VisibilityScope


class PersonaCreate(BaseModel):
    room_id: Optional[UUID] = None
    display_name: str = Field(..., min_length=2, max_length=64)
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    intent_mode: IntentMode = IntentMode.SOCIAL
    visibility_scope: VisibilityScope = VisibilityScope.ROOM_ONLY
    expires_at: Optional[datetime] = None


class PersonaResponse(BaseModel):
    id: UUID
    user_id: UUID
    room_id: Optional[UUID]
    display_name: str
    avatar_url: Optional[str]
    bio: Optional[str]
    intent_mode: IntentMode
    visibility_scope: VisibilityScope
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
