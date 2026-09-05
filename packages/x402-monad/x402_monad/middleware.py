"""
x402 HTTP Payment Protocol — FastAPI middleware

Zero Monad Mate dependencies. Drop into any FastAPI app.

Flow:
  1. Client hits your endpoint without X-Payment header
  2. Returns 402 with payment requirements (Base USDC)
  3. Client pays via Coinbase facilitator
  4. Client retries with X-Payment header (payment proof)
  5. Middleware verifies via https://x402.org/facilitator/verify
  6. Facilitator unreachable → graceful pass-through

References:
  - x402 spec: https://x402.org
  - Coinbase: https://docs.cdp.coinbase.com/x402
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# USDC on Base mainnet (ERC-20)
USDC_BASE_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
X402_FACILITATOR_VERIFY_URL = "https://x402.org/facilitator/verify"
X402_VERSION = 1
_MICRO_UNITS = 1_000_000  # USDC has 6 decimals


@dataclass
class X402Config:
    """Configuration for x402 payment middleware."""
    pay_to: str                              # Base wallet address to receive payment
    amount_usdc: float = 0.5                 # Amount in USDC (e.g. 0.5 = $0.50)
    asset: str = USDC_BASE_CONTRACT          # ERC-20 token address (default: USDC Base)
    network: str = "base"                    # Chain (base | base-sepolia)
    description: str = "API payment"        # Human-readable description in 402 body
    max_timeout_seconds: int = 300           # Payment window
    enabled: bool = True                     # Set False to bypass (dev/test)

    @property
    def amount_micro(self) -> str:
        """Amount in 6-decimal micro-units as string."""
        return str(int(self.amount_usdc * _MICRO_UNITS))


class X402PaymentRequired(Exception):
    """Raised internally to carry a 402 JSONResponse out of a dependency."""
    def __init__(self, response: JSONResponse):
        self.response = response


def x402_exception_handler(request: Request, exc: X402PaymentRequired):
    """Register this with app.add_exception_handler(X402PaymentRequired, ...)."""
    return exc.response


def _build_402_response(request: Request, config: X402Config) -> JSONResponse:
    body = {
        "x402Version": X402_VERSION,
        "error": "Payment required",
        "accepts": [{
            "scheme": "exact",
            "network": config.network,
            "maxAmountRequired": config.amount_micro,
            "resource": str(request.url),
            "description": config.description,
            "mimeType": "application/json",
            "payTo": config.pay_to,
            "maxTimeoutSeconds": config.max_timeout_seconds,
            "asset": config.asset,
            "extra": {"name": "USD Coin", "version": "2"},
        }],
    }
    return JSONResponse(status_code=402, content=body)


async def _verify_payment(payment_header: str, request: Request, config: X402Config) -> bool:
    payload = {
        "x402Version": X402_VERSION,
        "paymentHeader": payment_header,
        "requirements": {
            "scheme": "exact",
            "network": config.network,
            "maxAmountRequired": config.amount_micro,
            "resource": str(request.url),
            "payTo": config.pay_to,
            "asset": config.asset,
            "maxTimeoutSeconds": config.max_timeout_seconds,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(X402_FACILITATOR_VERIFY_URL, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                valid = data.get("isValid", False)
                if not valid:
                    logger.warning("x402 rejected: %s", data.get("invalidReason", "unknown"))
                return bool(valid)
            logger.warning("x402 facilitator status %d — pass-through", resp.status_code)
            return True  # graceful degradation
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.warning("x402 facilitator unreachable (%s) — pass-through", exc)
        return True  # graceful degradation


def require_x402_payment(config: X402Config):
    """
    Returns a FastAPI dependency that enforces x402 payment.

    Usage:
        @router.post("/dm", dependencies=[Depends(require_x402_payment(config))])
        async def send_dm(): ...
    """
    async def _dependency(request: Request) -> None:
        if not config.enabled:
            return

        payment_header = request.headers.get("X-Payment")
        if not payment_header:
            raise X402PaymentRequired(_build_402_response(request, config))

        is_valid = await _verify_payment(payment_header, request, config)
        if not is_valid:
            raise X402PaymentRequired(_build_402_response(request, config))

        logger.info("x402 payment verified for %s", request.url.path)

    return _dependency
