from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import uuid

from ..models.reputation import ReputationScore, ReputationEvent, ReputationEventType
from ..models.user import User
from ..schemas.reputation import FeedbackCreate


class SocialReputationService:
    def __init__(self, db: Session):
        self.db = db

    DIMENSION_MAP = {
        ReputationEventType.MEETUP_COMPLETED: ("meetup_completion_score", +5.0),
        ReputationEventType.MEETUP_NO_SHOW: ("meetup_completion_score", -15.0),
        ReputationEventType.MESSAGE_RESPONDED: ("response_score", +2.0),
        ReputationEventType.MESSAGE_IGNORED: ("response_score", -1.0),
        ReputationEventType.REPORT_RECEIVED: ("safety_score", -10.0),
        ReputationEventType.STAKE_SLASHED: ("reliability_score", -20.0),
        ReputationEventType.CONSENT_CONFIRMED: ("consent_confirmation_score", +3.0),
        ReputationEventType.POSITIVE_FEEDBACK: ("reliability_score", +3.0),
        ReputationEventType.NEGATIVE_FEEDBACK: ("reliability_score", -5.0),
    }

    def get_or_create(self, user_id: UUID) -> ReputationScore:
        score = self.db.query(ReputationScore).filter(ReputationScore.user_id == user_id).first()
        if not score:
            score = ReputationScore(id=uuid.uuid4(), user_id=user_id)
            self.db.add(score)
            self.db.commit()
            self.db.refresh(score)
        return score

    def get_by_persona(self, persona_id: UUID) -> ReputationScore:
        from ..models.persona import Persona
        persona = self.db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            from ..core.errors import PersonaNotFoundError
            raise PersonaNotFoundError()
        return self.get_or_create(persona.user_id)

    def record_feedback(self, reporter: User, payload: FeedbackCreate):
        score = self.get_or_create(payload.target_user_id)
        dimension, delta = self.DIMENSION_MAP.get(payload.event_type, ("reliability_score", 0.0))

        event = ReputationEvent(
            id=uuid.uuid4(),
            user_id=payload.target_user_id,
            event_type=payload.event_type,
            delta=delta,
            dimension=dimension,
            reference_id=payload.reference_id,
            notes=payload.notes,
        )
        self.db.add(event)
        self._apply_delta(score, dimension, delta)
        self._recalculate_composite(score)
        self.db.commit()
        return score

    def record_meetup_completed(self, user_id: UUID):
        score = self.get_or_create(user_id)
        score.total_meetups = (score.total_meetups or 0) + 1
        self._apply_delta(score, "meetup_completion_score", +5.0)
        self._apply_delta(score, "reliability_score", +3.0)
        self._recalculate_composite(score)
        self.db.commit()

    def process_attestation(self, attestation_id: UUID):
        from ..models.attestation import MeetupAttestation, AttestationStatus
        att = self.db.query(MeetupAttestation).filter(MeetupAttestation.id == attestation_id).first()
        if att and att.status == AttestationStatus.CONFIRMED:
            if att.initiator_user_id:
                self.record_meetup_completed(att.initiator_user_id)
            if att.counterparty_user_id:
                self.record_meetup_completed(att.counterparty_user_id)

    def _apply_delta(self, score: ReputationScore, dimension: str, delta: float):
        current = getattr(score, dimension, 50.0) or 50.0
        new_val = max(0.0, min(100.0, current + delta))
        setattr(score, dimension, new_val)
        score.updated_at = datetime.utcnow()

    def _recalculate_composite(self, score: ReputationScore):
        score.composite_score = (
            score.reliability_score * 0.25 +
            score.safety_score * 0.30 +
            score.response_score * 0.15 +
            score.meetup_completion_score * 0.20 +
            score.consent_confirmation_score * 0.10
        )
