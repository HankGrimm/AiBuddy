"""Reputation beat tasks — apply time-based score decay."""
import logging
from datetime import datetime, timedelta

from .celery_app import celery_app

logger = logging.getLogger(__name__)

# Scores decay toward the neutral midpoint (50.0) at this rate per day
_DECAY_RATE = 0.005          # 0.5 % per day
_NEUTRAL_MIDPOINT = 50.0
_DECAY_THRESHOLD_DAYS = 7    # only decay if not updated within this window


@celery_app.task(name="app.tasks.reputation_tasks.apply_reputation_decay", bind=True)
def apply_reputation_decay(self) -> dict:
    """Runs daily. Nudges each reputation score a small amount toward the
    neutral midpoint (50.0) for users who have been inactive for at least
    ``_DECAY_THRESHOLD_DAYS`` days.  This prevents stale high/low scores
    from persisting indefinitely.

    Returns a summary dict with counts for observability.
    """
    from app.core.database import SessionLocal
    from app.models.reputation import ReputationScore

    updated = 0
    errors = 0
    now = datetime.utcnow()
    cutoff = now - timedelta(days=_DECAY_THRESHOLD_DAYS)

    with SessionLocal() as db:
        scores = (
            db.query(ReputationScore)
            .filter(
                (ReputationScore.last_decay_at.is_(None)) |
                (ReputationScore.last_decay_at < cutoff)
            )
            .all()
        )
        logger.info("apply_reputation_decay: processing %d reputation records", len(scores))

        dimensions = [
            "reliability_score",
            "safety_score",
            "response_score",
            "meetup_completion_score",
            "consent_confirmation_score",
        ]

        for rec in scores:
            try:
                for dim in dimensions:
                    current = getattr(rec, dim)
                    # Move toward midpoint by decay rate
                    delta = (_NEUTRAL_MIDPOINT - current) * _DECAY_RATE
                    setattr(rec, dim, round(current + delta, 4))

                # Recompute simple composite as average of dimensions
                rec.composite_score = round(
                    sum(getattr(rec, d) for d in dimensions) / len(dimensions), 4
                )
                rec.last_decay_at = now
                updated += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to decay reputation for user %s: %s",
                    rec.user_id, exc, exc_info=True,
                )
                errors += 1

        try:
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to commit reputation decay batch: %s", exc, exc_info=True)
            db.rollback()
            errors += updated
            updated = 0

    result = {"updated": updated, "errors": errors, "ran_at": now.isoformat()}
    logger.info("apply_reputation_decay complete: %s", result)
    return result
