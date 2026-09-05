from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from ..models.user import VerificationLevel, PrivacyMode


class UserOnboard(BaseModel):
    wallet_address: str = Field(..., description="Monad (EVM) wallet address, 0x-prefixed")
    signature: str = Field(..., description="EIP-191 personal_sign of the nonce proving wallet ownership")
    nonce: str = Field(..., description="Challenge nonce")
    email: Optional[EmailStr] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    privacy_mode: Optional[PrivacyMode] = None


class UserResponse(BaseModel):
    id: UUID
    wallet_address: str
    did: Optional[str]
    age_verified: bool
    verification_level: VerificationLevel
    privacy_mode: PrivacyMode
    created_at: datetime

    class Config:
        from_attributes = True


class WalletAuthChallenge(BaseModel):
    nonce: str
    expires_at: datetime


class WalletAuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
