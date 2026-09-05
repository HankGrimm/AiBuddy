"""
Hedera Consensus Service (HCS) anchoring for reputation events.

Publishes tamper-proof audit records to Hedera HCS.
Gracefully no-ops when HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY are not set.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

_HEDERA_MIRROR_REST = {
    "mainnet": "https://mainnet-public.mirrornode.hedera.com/api/v1",
    "testnet": "https://testnet.mirrornode.hedera.com/api/v1",
    "previewnet": "https://previewnet.mirrornode.hedera.com/api/v1",
}


class HCSAnchor:
    """
    Publishes reputation and safety events to Hedera Consensus Service.

    Args:
        topic_id:      HCS topic ID (e.g. "0.0.1234567"). Create once, reuse forever.
        account_id:    Hedera account ID (e.g. "0.0.9876"). Defaults to env HEDERA_ACCOUNT_ID.
        private_key:   Hedera ED25519 private key hex. Defaults to env HEDERA_PRIVATE_KEY.
        network:       "mainnet" | "testnet" | "previewnet". Defaults to env HEDERA_NETWORK.
    """

    def __init__(
        self,
        topic_id: Optional[str] = None,
        account_id: Optional[str] = None,
        private_key: Optional[str] = None,
        network: Optional[str] = None,
    ):
        self.topic_id = topic_id or os.getenv("HEDERA_TOPIC_ID")
        self.account_id = account_id or os.getenv("HEDERA_ACCOUNT_ID")
        self.private_key = private_key or os.getenv("HEDERA_PRIVATE_KEY")
        self.network = network or os.getenv("HEDERA_NETWORK", "testnet")
        self._mirror = _HEDERA_MIRROR_REST.get(self.network, _HEDERA_MIRROR_REST["testnet"])

    @property
    def is_configured(self) -> bool:
        return bool(self.topic_id and self.account_id and self.private_key)

    def anchor_reputation_event(
        self,
        user_id: str,
        event_type: str,
        dimension_deltas: dict,
        composite_before: float,
        composite_after: float,
        reference_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Publish a reputation event to HCS.

        Returns the HCS sequence number on success, None on failure.
        """
        payload = {
            "type": "reputation_event",
            "user_id": user_id,
            "event_type": event_type,
            "dimension_deltas": dimension_deltas,
            "composite_before": composite_before,
            "composite_after": composite_after,
            "reference_id": reference_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return self._publish(payload)

    def anchor_safety_action(
        self,
        action_type: str,
        actor_id: str,
        subject_id: str,
        reason: str,
        severity: str,
        reference_id: Optional[str] = None,
    ) -> Optional[str]:
        """Publish a safety/moderation action to HCS."""
        payload = {
            "type": "safety_action",
            "action_type": action_type,
            "actor_id": actor_id,
            "subject_id": subject_id,
            "reason": reason,
            "severity": severity,
            "reference_id": reference_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return self._publish(payload)

    def anchor_stake_decision(
        self,
        stake_id: str,
        user_id: str,
        decision: str,  # "refund" | "slash"
        amount_usdc: float,
        reason: Optional[str] = None,
    ) -> Optional[str]:
        """Publish a stake refund or slash decision to HCS."""
        payload = {
            "type": "stake_decision",
            "stake_id": stake_id,
            "user_id": user_id,
            "decision": decision,
            "amount_usdc": amount_usdc,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return self._publish(payload)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, payload: dict) -> Optional[str]:
        if not self.is_configured:
            logger.debug("HCS not configured — skipping anchor for %s", payload.get("type"))
            return None

        message = json.dumps(payload, separators=(",", ":"))

        try:
            resp = httpx.post(
                f"{self._mirror}/topics/{self.topic_id}/messages",
                json={
                    "message": message,
                    "payer_account_id": self.account_id,
                },
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.private_key or "",
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                seq = resp.json().get("sequence_number")
                logger.info("HCS anchored %s → seq %s", payload.get("type"), seq)
                return str(seq) if seq else "ok"
            logger.warning("HCS publish HTTP %s: %s", resp.status_code, resp.text[:80])
        except Exception as exc:
            logger.warning("HCS publish error: %s", exc)

        return None
