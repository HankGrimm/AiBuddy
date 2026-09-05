from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
import uuid

from ..models.reputation import ReputationScore, ReputationEvent, ReputationEventType


_DIMENSION_MAP = {
    ReputationEventType.MEETUP_COMPLETED: ("meetup_completion_score", +5.0),
    ReputationEventType.MEETUP_NO_SHOW:   ("meetup_completion_score", -15.0),
    ReputationEventType.MESSAGE_RESPONDED: ("response_score", +2.0),
    ReputationEventType.MESSAGE_IGNORED:  ("response_score", -1.0),
    ReputationEventType.REPORT_RECEIVED:  ("safety_score", -10.0),
    ReputationEventType.STAKE_SLASHED:    ("reliability_score", -20.0),
    ReputationEventType.CONSENT_CONFIRMED: ("consent_confirmation_score", +3.0),
    ReputationEventType.POSITIVE_FEEDBACK: ("reliability_score", +3.0),
    ReputationEventType.NEGATIVE_FEEDBACK: ("reliability_score", -5.0),
}


class ReputationEventProcessor:
    """Processes discrete reputation events and persists the resulting score."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ public
    def process_event(self, event: ReputationEvent) -> ReputationScore:
        """
        Persist *event* and apply its delta to the user's ReputationScore.
        Returns the updated score.
        """
        self.db.add(event)
        score = self._get_or_create(event.user_id)
        self._apply_delta(score, event.dimension, event.delta)
        self._recalculate_composite(score)
        self.db.commit()
        self.db.refresh(score)
        return score

    def process_meetup_completed(self, user_id: UUID, match_id: UUID) -> ReputationScore:
        """Record a successful meetup for *user_id*."""
        dimension, delta = _DIMENSION_MAP[ReputationEventType.MEETUP_COMPLETED]
        event = ReputationEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            event_type=ReputationEventType.MEETUP_COMPLETED,
            delta=delta,
            dimension=dimension,
            reference_id=match_id,
        )
        score = self.process_event(event)
        # Also increment total_meetups counter
        score.total_meetups = (score.total_meetups or 0) + 1
        self.db.commit()
        self.db.refresh(score)
        return score

    def process_no_show(self, user_id: UUID, match_id: UUID) -> ReputationScore:
        """Record a no-show penalty for *user_id*."""
        dimension, delta = _DIMENSION_MAP[ReputationEventType.MEETUP_NO_SHOW]
        event = ReputationEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            event_type=ReputationEventType.MEETUP_NO_SHOW,
            delta=delta,
            dimension=dimension,
            reference_id=match_id,
        )
        return self.process_event(event)

    def get_event_history(
        self, user_id: UUID, limit: int = 50
    ) -> list[ReputationEvent]:
        """Return up to *limit* most-recent reputation events for *user_id*."""
        return (
            self.db.query(ReputationEvent)
            .filter(ReputationEvent.user_id == user_id)
            .order_by(ReputationEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------ helpers
    def _get_or_create(self, user_id: UUID) -> ReputationScore:
        score = (
            self.db.query(ReputationScore)
            .filter(ReputationScore.user_id == user_id)
            .first()
        )
        if not score:
            score = ReputationScore(id=uuid.uuid4(), user_id=user_id)
            self.db.add(score)
            self.db.commit()
            self.db.refresh(score)
        return score

    @staticmethod
    def _apply_delta(score: ReputationScore, dimension: str, delta: float):
        current = getattr(score, dimension, 50.0) or 50.0
        setattr(score, dimension, max(0.0, min(100.0, current + delta)))
        score.updated_at = datetime.utcnow()

    @staticmethod
    def _recalculate_composite(score: ReputationScore):
        score.composite_score = (
            score.reliability_score * 0.25
            + score.safety_score * 0.30
            + score.response_score * 0.15
            + score.meetup_completion_score * 0.20
            + score.consent_confirmation_score * 0.10
        )
