"""Match beat tasks — expire stale pending matches."""
import logging
from datetime import datetime

from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.match_tasks.expire_stale_matches", bind=True)
def expire_stale_matches(self) -> dict:
    """Runs every hour. Marks pending matches as EXPIRED when their
    ``expires_at`` deadline has passed without a response.

    Returns a summary dict with counts for observability.
    """
    from app.core.database import SessionLocal
    from app.models.match import Match, MatchStatus

    expired_count = 0
    errors = 0

    with SessionLocal() as db:
        now = datetime.utcnow()
        stale = (
            db.query(Match)
            .filter(
                Match.status == MatchStatus.PENDING,
                Match.expires_at.isnot(None),
                Match.expires_at < now,
            )
            .all()
        )
        logger.info("expire_stale_matches: found %d stale matches", len(stale))

        for match in stale:
            try:
                match.status = MatchStatus.EXPIRED
                expired_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to expire match %s: %s", match.id, exc, exc_info=True
                )
                errors += 1

        try:
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to commit match expiry batch: %s", exc, exc_info=True)
            db.rollback()
            errors += expired_count
            expired_count = 0

    result = {"expired": expired_count, "errors": errors, "ran_at": datetime.utcnow().isoformat()}
    logger.info("expire_stale_matches complete: %s", result)
    return result
