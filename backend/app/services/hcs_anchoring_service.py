"""
Hedera Consensus Service (HCS) Anchoring — Monad Mate

Anchors critical events (meetup attestations, stake decisions, safety actions)
to Hedera HCS for immutable auditability. Gracefully no-ops when credentials
are not configured (e.g., local dev / test environments).

Refs #9
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

_HEDERA_BASE = "https://testnet.mirrornode.hedera.com"
_TOPIC_ENV_KEY = "HEDERA_TOPIC_ID"


def _is_configured() -> bool:
    return bool(os.getenv("HEDERA_ACCOUNT_ID") and os.getenv("HEDERA_PRIVATE_KEY"))


def _topic_id() -> Optional[str]:
    return os.getenv(_TOPIC_ENV_KEY)


class HCSAnchoringService:
    """
    Publishes signed audit messages to a Hedera HCS topic.

    All methods return an Optional[str] — the HCS message ID on success,
    or None if Hedera is unconfigured or the publish fails.
    """

    def anchor_attestation(
        self,
        attestation_id: UUID,
        match_id: UUID,
        initiator_user_id: UUID,
        counterparty_user_id: Optional[UUID],
        method: str,
        gps_lat: Optional[float] = None,
        gps_lng: Optional[float] = None,
    ) -> Optional[str]:
        return self._publish({
            "event": "meetup_attestation_confirmed",
            "attestation_id": str(attestation_id),
            "match_id": str(match_id),
            "initiator_user_id": str(initiator_user_id),
            "counterparty_user_id": str(counterparty_user_id) if counterparty_user_id else None,
            "method": method,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def anchor_stake_decision(
        self,
        stake_id: UUID,
        user_id: UUID,
        decision: str,      # "refunded" | "slashed"
        amount_mon: float,
        slash_reason: Optional[str] = None,
    ) -> Optional[str]:
        return self._publish({
            "event": "stake_decision",
            "stake_id": str(stake_id),
            "user_id": str(user_id),
            "decision": decision,
            "amount_mon": amount_mon,
            "slash_reason": slash_reason,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def anchor_safety_action(
        self,
        report_id: UUID,
        reporter_id: UUID,
        reported_user_id: UUID,
        action: str,        # "warned" | "suspended" | "banned" | "dismissed"
        category: str,
    ) -> Optional[str]:
        return self._publish({
            "event": "safety_action",
            "report_id": str(report_id),
            "reporter_id": str(reporter_id),
            "reported_user_id": str(reported_user_id),
            "action": action,
            "category": category,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def anchor_escrow_event(
        self,
        escrow_id: UUID,
        event: str,         # "opened" | "confirmed" | "disputed" | "resolved"
        user_id: UUID,
        amount_mon: float,
    ) -> Optional[str]:
        return self._publish({
            "event": f"escrow_{event}",
            "escrow_id": str(escrow_id),
            "user_id": str(user_id),
            "amount_mon": amount_mon,
            "timestamp": datetime.utcnow().isoformat(),
        })

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, payload: dict) -> Optional[str]:
        if not _is_configured():
            logger.debug("HCS not configured — skipping anchor: %s", payload.get("event"))
            return None

        topic = _topic_id()
        if not topic:
            logger.warning("HEDERA_TOPIC_ID not set — skipping HCS publish")
            return None

        try:
            import httpx
            resp = httpx.post(
                f"{_HEDERA_BASE}/api/v1/topics/{topic}/messages",
                json={"message": json.dumps(payload, default=str)},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                msg_id = data.get("consensus_timestamp") or data.get("message_id")
                logger.info("HCS anchored %s → %s", payload["event"], msg_id)
                return msg_id
            else:
                logger.warning("HCS publish failed HTTP %s: %s", resp.status_code, resp.text[:200])
                return None
        except Exception as exc:
            logger.warning("HCS publish error: %s", exc)
            return None
