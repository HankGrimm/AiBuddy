"""
x402 HTTP Payment Protocol middleware for Monad Mate.

Implements Coinbase x402 payment verification for DM unlock staking.
Protocol: https://x402.org

Flow:
  1. Client hits POST /api/v1/stakes (stake_type=dm) without X-Payment header
  2. Server returns HTTP 402 with payment requirements (Base USDC)
  3. Client pays on Base via Coinbase facilitator
  4. Client retries with X-Payment header containing payment proof
  5. Server verifies proof via https://x402.org/facilitator/verify
  6. If verified, request proceeds; if facilitator unreachable, allow through

Usage:
  from app.middleware.x402_payment import require_x402_payment
  router.post("/v1/stakes", dependencies=[Depends(require_x402_payment)])
"""

import logging
from typing import Any

import httpx
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from ..core.config import settings

logger = logging.getLogger(__name__)

# USDC on Base mainnet (ERC-20)
USDC_BASE_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
# 0.5 USDC in micro-units (6 decimals)
DM_UNLOCK_AMOUNT = "500000"

X402_FACILITATOR_VERIFY_URL = "https://x402.org/facilitator/verify"
X402_VERSION = 1


def _build_402_response(request: Request) -> JSONResponse:
    """Return the x402 payment required response body per the x402 spec."""
    resource_url = str(request.url)
    pay_to = settings.COINBASE_PAYMENT_ADDRESS or "0x0000000000000000000000000000000000000000"

    body = {
        "x402Version": X402_VERSION,
        "error": "Payment required to unlock DMs",
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": DM_UNLOCK_AMOUNT,
                "resource": resource_url,
                "description": "Monad Mate DM unlock — stake required",
                "mimeType": "application/json",
                "payTo": pay_to,
                "maxTimeoutSeconds": 300,
                "asset": USDC_BASE_CONTRACT,
                "extra": {
                    "name": "USD Coin",
                    "version": "2",
                },
            }
        ],
    }
    return JSONResponse(status_code=402, content=body)


async def _verify_payment_with_facilitator(payment_header: str, request: Request) -> bool:
    """
    Verify an x402 payment header against the Coinbase facilitator.

    Returns True if valid, False if invalid.
    Raises no exceptions — network failures are logged and treated as pass-through.
    """
    payload = {
        "x402Version": X402_VERSION,
        "paymentHeader": payment_header,
        "requirements": {
            "scheme": "exact",
            "network": "base",
            "maxAmountRequired": DM_UNLOCK_AMOUNT,
            "resource": str(request.url),
            "payTo": settings.COINBASE_PAYMENT_ADDRESS or "0x0000000000000000000000000000000000000000",
            "asset": USDC_BASE_CONTRACT,
            "maxTimeoutSeconds": 300,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(X402_FACILITATOR_VERIFY_URL, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                valid = data.get("isValid", False)
                if not valid:
                    logger.warning("x402 facilitator rejected payment: %s", data.get("invalidReason", "unknown"))
                return bool(valid)
            else:
                logger.warning(
                    "x402 facilitator returned unexpected status %d — allowing through",
                    resp.status_code,
                )
                return True
    except httpx.TimeoutException:
        logger.warning("x402 facilitator timed out — allowing request through (graceful degradation)")
        return True
    except httpx.RequestError as exc:
        logger.warning("x402 facilitator unreachable (%s) — allowing request through", exc)
        return True


class X402PaymentRequired(Exception):
    """Raised internally when 402 must be returned."""

    def __init__(self, response: JSONResponse):
        self.response = response


async def require_x402_payment(request: Request) -> None:
    """
    FastAPI dependency that enforces x402 payment for DM unlock.

    - No X-Payment header → returns HTTP 402 with payment requirements
    - X-Payment header present → verifies via Coinbase facilitator
    - Facilitator unreachable → allow through (graceful degradation)
    - Invalid payment → returns HTTP 402

    Only active when X402_ENABLED=true in config.
    """
    if not settings.X402_ENABLED:
        return

    payment_header = request.headers.get("X-Payment")

    if not payment_header:
        # Return 402 inline by raising an exception caught by the endpoint,
        # or by returning the response directly.
        # FastAPI dependencies can't return responses directly, so we use a
        # workaround: store the 402 response on the request state for the
        # endpoint to return, OR we raise HTTPException with a custom response.
        # The cleanest approach for x402 is using a custom exception handler.
        raise _X402Exception(_build_402_response(request))

    # Payment header present — verify it
    is_valid = await _verify_payment_with_facilitator(payment_header, request)
    if not is_valid:
        raise _X402Exception(_build_402_response(request))

    logger.info("x402 payment verified for %s", request.url.path)


class _X402Exception(Exception):
    """Internal exception to carry the 402 JSONResponse out of a dependency."""

    def __init__(self, response: JSONResponse):
        self.response = response
