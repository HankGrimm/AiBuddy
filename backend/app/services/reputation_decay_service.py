from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from uuid import UUID

from ..models.reputation import ReputationScore


_DECAY_PER_WEEK = 1.0  # points lost per dimension per week of inactivity
_DECAY_DIMENSIONS = [
    "reliability_score",
    "safety_score",
    "response_score",
    "meetup_completion_score",
    "consent_confirmation_score",
]


class ReputationDecayService:
    """Applies time-based reputation decay for inactive users."""

    def __init__(self, db: Session):
        self.db = db

    def apply_decay(self, user_id: UUID) -> ReputationScore:
        """
        Apply -1 point per full week of inactivity to every reputation dimension
        for a single user.  Updates last_decay_at and composite_score.
        """
        score = self.db.query(ReputationScore).filter(
            ReputationScore.user_id == user_id
        ).first()
        if not score:
            return score  # nothing to decay

        now = datetime.utcnow()
        last = score.last_decay_at or score.updated_at or now

        weeks_inactive = int((now - last).total_seconds() / (7 * 24 * 3600))
        if weeks_inactive < 1:
            return score

        decay_amount = _DECAY_PER_WEEK * weeks_inactive
        for dim in _DECAY_DIMENSIONS:
            current = getattr(score, dim, 50.0) or 50.0
            setattr(score, dim, max(0.0, current - decay_amount))

        score.last_decay_at = now
        score.composite_score = self._composite(score)
        self.db.commit()
        self.db.refresh(score)
        return score

    def apply_bulk_decay(self, days_inactive_threshold: int = 7) -> int:
        """
        Apply decay to all users whose last_decay_at (or updated_at) is older than
        *days_inactive_threshold* days.  Returns the number of records processed.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_inactive_threshold)

        scores = (
            self.db.query(ReputationScore)
            .filter(
                (ReputationScore.last_decay_at == None)  # noqa: E711
                | (ReputationScore.last_decay_at < cutoff)
            )
            .all()
        )

        count = 0
        for score in scores:
            self.apply_decay(score.user_id)
            count += 1
        return count

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _composite(score: ReputationScore) -> float:
        return (
            score.reliability_score * 0.25
            + score.safety_score * 0.30
            + score.response_score * 0.15
            + score.meetup_completion_score * 0.20
            + score.consent_confirmation_score * 0.10
        )
