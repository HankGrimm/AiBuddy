from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from ..core.database import get_db
from ..core.auth import get_current_user
from ..core.config import settings
from ..models.user import User
from ..models.stake import StakeType
from ..schemas.stake import StakeCreate, StakeResponse, StakeSlash
from ..schemas.escrow import EscrowCreate, EscrowResponse, EscrowDispute
from ..services.stake_service import StakeService
from ..services.escrow_service import EscrowService
from ..middleware.x402_payment import require_x402_payment

router = APIRouter(tags=["stakes"])


@router.post("/v1/stakes", response_model=StakeResponse, status_code=201)
async def create_stake(
    request: Request,
    payload: StakeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Apply x402 payment check for DM unlock when enabled
    if settings.X402_ENABLED and payload.stake_type == StakeType.DM:
        await require_x402_payment(request)

    svc = StakeService(db)
    return svc.create(current_user, payload)


@router.get("/v1/stakes/me", response_model=List[StakeResponse])
async def my_stakes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = StakeService(db)
    return svc.get_user_stakes(current_user.id)


@router.post("/v1/stakes/{stake_id}/refund", response_model=StakeResponse)
async def refund_stake(
    stake_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = StakeService(db)
    return svc.refund(current_user, stake_id)


@router.post("/v1/stakes/{stake_id}/slash", response_model=StakeResponse)
async def slash_stake(
    stake_id: UUID,
    payload: StakeSlash,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = StakeService(db)
    return svc.slash(current_user, stake_id, payload.reason)


# Escrow endpoints
@router.post("/v1/escrow/meetup", response_model=EscrowResponse, status_code=201)
async def create_meetup_escrow(
    payload: EscrowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = EscrowService(db)
    return svc.create_meetup(current_user, payload)


@router.post("/v1/escrow/{escrow_id}/confirm", response_model=EscrowResponse)
async def confirm_escrow(
    escrow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = EscrowService(db)
    return svc.confirm(current_user, escrow_id)


@router.post("/v1/escrow/{escrow_id}/dispute", response_model=EscrowResponse)
async def dispute_escrow(
    escrow_id: UUID,
    payload: EscrowDispute,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = EscrowService(db)
    return svc.dispute(current_user, escrow_id, payload.reason)
