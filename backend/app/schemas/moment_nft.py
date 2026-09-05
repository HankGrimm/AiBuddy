"""
Pydantic schemas for Moment NFT endpoints.
Refs #17
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from ..models.moment_nft import MomentNFTStatus


class MintMomentRequest(BaseModel):
    attestation_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class MomentNFTResponse(BaseModel):
    id: UUID
    owner_id: UUID
    attestation_id: UUID
    mint_address: Optional[str]
    metadata_uri: Optional[str]
    name: str
    description: Optional[str]
    status: MomentNFTStatus
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class MomentNFTListResponse(BaseModel):
    items: List[MomentNFTResponse]
    total: int
    limit: int
    offset: int
