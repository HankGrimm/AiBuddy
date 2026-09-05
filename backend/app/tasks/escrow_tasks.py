"""Escrow beat tasks — automatically slash expired escrows."""
import logging
from datetime import datetime

from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.escrow_tasks.auto_slash_expired_escrows", bind=True)
def auto_slash_expired_escrows(self) -> dict:
    """Runs every hour. Finds escrows past their deadline with no release/slash
    signal and applies the configured slashing policy.

    Returns a summary dict with counts for observability.
    """
    from app.core.database import SessionLocal
    from app.models.escrow import Escrow
    from app.services.slashing_policy_service import SlashingPolicyService

    slashed = 0
    errors = 0

    with SessionLocal() as db:
        now = datetime.utcnow()
        from app.models.escrow import EscrowStatus
        expired = (
            db.query(Escrow)
            .filter(
                Escrow.confirm_deadline < now,
                Escrow.status == EscrowStatus.OPEN,
            )
            .all()
        )
        logger.info("auto_slash_expired_escrows: found %d expired escrows", len(expired))

        svc = SlashingPolicyService(db)
        for escrow in expired:
            try:
                svc.slash(escrow)
                slashed += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to slash escrow %s: %s", escrow.id, exc, exc_info=True
                )
                errors += 1

    result = {"slashed": slashed, "errors": errors, "ran_at": datetime.utcnow().isoformat()}
    logger.info("auto_slash_expired_escrows complete: %s", result)
    return result
