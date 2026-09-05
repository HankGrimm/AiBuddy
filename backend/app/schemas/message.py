from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from ..models.message import MessageType


class MessageCreate(BaseModel):
    match_id: UUID
    content: str = Field(..., min_length=1, max_length=2000)
    type: MessageType = MessageType.TEXT
    stake_id: Optional[UUID] = None


class MessageResponse(BaseModel):
    id: UUID
    match_id: UUID
    sender_persona_id: Optional[UUID]
    type: MessageType
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MessageThread(BaseModel):
    messages: List[MessageResponse]
    total: int
    match_id: UUID
