from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.reputation import ReputationResponse, FeedbackCreate
from ..services.social_reputation_service import SocialReputationService

router = APIRouter(prefix="/v1/reputation", tags=["reputation"])


@router.get("/me", response_model=ReputationResponse)
async def my_reputation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SocialReputationService(db)
    return svc.get_or_create(current_user.id)


@router.get("/persona/{persona_id}", response_model=ReputationResponse)
async def persona_reputation(
    persona_id: UUID,
    db: Session = Depends(get_db),
):
    svc = SocialReputationService(db)
    return svc.get_by_persona(persona_id)


@router.post("/feedback", status_code=201)
async def submit_feedback(
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SocialReputationService(db)
    return svc.record_feedback(current_user, payload)


@router.post("/attestation-score", status_code=200)
async def update_attestation_score(
    attestation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SocialReputationService(db)
    return svc.process_attestation(attestation_id)
