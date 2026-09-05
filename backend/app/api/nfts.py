"""
Moment NFT API endpoints — mint and list NFTs for confirmed meetups.
Refs #17
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.moment_nft import (
    MintMomentRequest,
    MomentNFTResponse,
    MomentNFTListResponse,
)
from ..services.moment_nft_service import MomentNFTService

router = APIRouter(prefix="/v1/nfts", tags=["nfts"])


@router.post("/mint-moment", response_model=MomentNFTResponse, status_code=201)
async def mint_moment(
    payload: MintMomentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint a Moment NFT for a confirmed meetup attestation."""
    svc = MomentNFTService(db)
    return svc.mint_moment(current_user, payload)


@router.get("/moments", response_model=MomentNFTListResponse)
async def list_moments(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List Moment NFTs owned by the authenticated user."""
    svc = MomentNFTService(db)
    items, total = svc.list_user_moments(current_user.id, limit=limit, offset=offset)
    return MomentNFTListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
