"""
x402-monad — FastAPI x402 HTTP Payment Protocol middleware

Bridges Coinbase x402 HTTP payments on Base with FastAPI apps.
Works standalone with any FastAPI service — no Monad Mate dependencies.

Install: pip install x402-monad
Usage:
    from x402_monad import require_x402_payment, X402Config
    config = X402Config(pay_to="0xYourAddress", amount_usdc=0.5, enabled=True)
    app.add_exception_handler(X402PaymentRequired, x402_exception_handler)

    @router.post("/premium-endpoint", dependencies=[Depends(require_x402_payment(config))])
    async def my_endpoint(): ...
"""

from .middleware import require_x402_payment, X402Config, X402PaymentRequired, x402_exception_handler

__version__ = "0.1.0"
__all__ = ["require_x402_payment", "X402Config", "X402PaymentRequired", "x402_exception_handler"]
