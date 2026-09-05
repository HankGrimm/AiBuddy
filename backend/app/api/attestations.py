from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.attestation import AttestationInitiate, AttestationConfirm, AttestationResponse
from ..services.meetup_attestation_service import MeetupAttestationService

router = APIRouter(prefix="/v1/attestations", tags=["attestations"])


@router.post("/meetup/initiate", response_model=AttestationResponse, status_code=201)
async def initiate_meetup_attestation(
    payload: AttestationInitiate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MeetupAttestationService(db)
    return svc.initiate(current_user, payload)


@router.post("/meetup/{attestation_id}/confirm", response_model=AttestationResponse)
async def confirm_meetup_attestation(
    attestation_id: UUID,
    payload: AttestationConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MeetupAttestationService(db)
    return svc.confirm(current_user, attestation_id, payload)


@router.post("/proximity", response_model=AttestationResponse)
async def verify_proximity(
    payload: AttestationInitiate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MeetupAttestationService(db)
    return svc.verify_proximity(current_user, payload)


@router.get("/me", response_model=List[AttestationResponse])
async def my_attestations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MeetupAttestationService(db)
    return svc.get_user_attestations(current_user.id)
