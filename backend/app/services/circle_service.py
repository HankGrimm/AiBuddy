"""
Circle USDC Service — Monad Mate

Handles USDC transfers for stake creation, refund, and slash via the Circle API.
Falls back to stub mode (logs only) when CIRCLE_API_KEY is not configured.

Refs #9
"""
import logging
import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

_CIRCLE_BASE = {
    "sandbox": "https://api-sandbox.circle.com/v1",
    "production": "https://api.circle.com/v1",
}


def _api_key() -> Optional[str]:
    return os.getenv("CIRCLE_API_KEY")


def _env() -> str:
    return os.getenv("CIRCLE_ENVIRONMENT", "sandbox")


def _entity_secret() -> Optional[str]:
    return os.getenv("CIRCLE_ENTITY_SECRET")


def _is_configured() -> bool:
    return bool(_api_key()) and bool(_entity_secret())


@dataclass
class TransferResult:
    success: bool
    transfer_id: Optional[str]
    status: str          # "pending" | "complete" | "failed" | "stub"
    error: Optional[str] = None


class CircleService:
    """
    Thin wrapper around the Circle Payments API for USDC escrow flows.

    - debit_stake: move USDC from user wallet to Monad Mate escrow wallet
    - credit_refund: return USDC from escrow to user wallet
    - transfer_slash: move slashed USDC from escrow to safety fund wallet
    """

    def debit_stake(
        self,
        source_wallet_id: str,
        amount_usdc: float,
        stake_id: UUID,
        idempotency_key: Optional[str] = None,
    ) -> TransferResult:
        """Debit USDC from user wallet into escrow on stake creation."""
        return self._transfer(
            source=source_wallet_id,
            destination=os.getenv("CIRCLE_ESCROW_WALLET_ID", "escrow_wallet"),
            amount_usdc=amount_usdc,
            idempotency_key=idempotency_key or f"stake-{stake_id}",
            memo=f"Monad Mate stake {stake_id}",
        )

    def credit_refund(
        self,
        destination_wallet_id: str,
        amount_usdc: float,
        stake_id: UUID,
        idempotency_key: Optional[str] = None,
    ) -> TransferResult:
        """Return USDC from escrow to user wallet on stake refund."""
        return self._transfer(
            source=os.getenv("CIRCLE_ESCROW_WALLET_ID", "escrow_wallet"),
            destination=destination_wallet_id,
            amount_usdc=amount_usdc,
            idempotency_key=idempotency_key or f"refund-{stake_id}",
            memo=f"Monad Mate refund {stake_id}",
        )

    def transfer_slash(
        self,
        amount_usdc: float,
        stake_id: UUID,
        reason: str,
        idempotency_key: Optional[str] = None,
    ) -> TransferResult:
        """Move slashed USDC from escrow to safety fund wallet."""
        return self._transfer(
            source=os.getenv("CIRCLE_ESCROW_WALLET_ID", "escrow_wallet"),
            destination=os.getenv("CIRCLE_SAFETY_FUND_WALLET_ID", "safety_fund_wallet"),
            amount_usdc=amount_usdc,
            idempotency_key=idempotency_key or f"slash-{stake_id}",
            memo=f"Monad Mate slash {stake_id}: {reason}",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _transfer(
        self,
        source: str,
        destination: str,
        amount_usdc: float,
        idempotency_key: str,
        memo: str,
    ) -> TransferResult:
        if not _is_configured():
            logger.debug(
                "Circle not configured — stub transfer %.2f USDC [%s]",
                amount_usdc, idempotency_key,
            )
            return TransferResult(
                success=True,
                transfer_id=f"stub-{idempotency_key}",
                status="stub",
            )

        try:
            import httpx
            base = _CIRCLE_BASE[_env()]
            resp = httpx.post(
                f"{base}/transfers",
                json={
                    "idempotencyKey": idempotency_key,
                    "source": {"type": "wallet", "id": source},
                    "destination": {"type": "wallet", "id": destination},
                    "amount": {"amount": f"{amount_usdc:.2f}", "currency": "USD"},
                    "memo": memo,
                },
                headers={
                    "Authorization": f"Bearer {_api_key()}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            data = resp.json().get("data", {})
            if resp.status_code in (200, 201):
                logger.info("Circle transfer %s: %s", data.get("id"), data.get("status"))
                return TransferResult(
                    success=True,
                    transfer_id=data.get("id"),
                    status=data.get("status", "pending"),
                )
            else:
                error = resp.json().get("message", resp.text[:100])
                logger.warning("Circle transfer failed: %s", error)
                return TransferResult(success=False, transfer_id=None, status="failed", error=error)
        except Exception as exc:
            logger.warning("Circle transfer error: %s", exc)
            return TransferResult(success=False, transfer_id=None, status="failed", error=str(exc))
