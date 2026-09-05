from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
import uuid

from ..models.persona import Persona
from ..models.user import User
from ..schemas.persona import PersonaCreate
from ..core.errors import PersonaNotFoundError


class PersonaService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, payload: PersonaCreate) -> Persona:
        persona = Persona(
            id=uuid.uuid4(),
            user_id=user.id,
            room_id=payload.room_id,
            display_name=payload.display_name,
            avatar_url=payload.avatar_url,
            bio=payload.bio,
            intent_mode=payload.intent_mode,
            visibility_scope=payload.visibility_scope,
            expires_at=payload.expires_at,
        )
        self.db.add(persona)
        self.db.commit()
        self.db.refresh(persona)
        return persona

    def get_user_personas(self, user_id: UUID) -> list[Persona]:
        return (
            self.db.query(Persona)
            .filter(Persona.user_id == user_id, Persona.is_active == True)
            .all()
        )

    def get_or_404(self, persona_id: UUID) -> Persona:
        p = self.db.query(Persona).filter(Persona.id == persona_id).first()
        if not p:
            raise PersonaNotFoundError()
        return p

    def deactivate(self, user: User, persona_id: UUID):
        p = self.db.query(Persona).filter(
            Persona.id == persona_id, Persona.user_id == user.id
        ).first()
        if not p:
            raise PersonaNotFoundError()
        p.is_active = False
        self.db.commit()

    def validate_active(self, persona: Persona):
        from ..core.errors import PersonaExpiredError
        if not persona.is_active:
            raise PersonaExpiredError()
        if persona.expires_at and persona.expires_at < datetime.utcnow():
            persona.is_active = False
            self.db.commit()
            raise PersonaExpiredError()
