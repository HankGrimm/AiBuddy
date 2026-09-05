from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.persona import PersonaCreate, PersonaResponse
from ..services.persona_service import PersonaService

router = APIRouter(prefix="/v1/personas", tags=["personas"])


@router.post("", response_model=PersonaResponse, status_code=201)
async def create_persona(
    payload: PersonaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PersonaService(db)
    return svc.create(current_user, payload)


@router.get("/me", response_model=list[PersonaResponse])
async def get_my_personas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PersonaService(db)
    return svc.get_user_personas(current_user.id)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PersonaService(db)
    svc.deactivate(current_user, persona_id)
