# x402-monad

> FastAPI middleware for the [Coinbase x402](https://x402.org) HTTP payment protocol on Base USDC.

[![PyPI](https://img.shields.io/pypi/v/x402-monad)](https://pypi.org/project/x402-monad/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

**Novel cross-chain primitive:** bridges Monad wallet authentication with Coinbase x402 HTTP payments on Base — extracted from Monad Mate Trust API.

## Install

```bash
pip install x402-monad
```

## Usage

```python
from fastapi import FastAPI, Depends
from x402_monad import require_x402_payment, X402Config, X402PaymentRequired, x402_exception_handler

app = FastAPI()
app.add_exception_handler(X402PaymentRequired, x402_exception_handler)

config = X402Config(
    pay_to="0xYourBaseWalletAddress",
    amount_usdc=0.5,            # $0.50 USDC per request
    description="DM unlock",
    enabled=True,               # Set False to bypass in dev
)

@app.post("/dm/send", dependencies=[Depends(require_x402_payment(config))])
async def send_dm(body: dict):
    return {"status": "sent"}
```

## Flow

```
Client → POST /dm/send (no X-Payment header)
Server → 402 Payment Required + {x402Version, accepts: [{network, asset, amount, payTo}]}
Client → pays 0.5 USDC on Base via Coinbase facilitator
Client → POST /dm/send (X-Payment: <proof>)
Server → verifies proof via https://x402.org/facilitator/verify
Server → 200 OK (request processed)
```

## Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `pay_to` | required | Base wallet address to receive USDC |
| `amount_usdc` | `0.5` | Payment amount in USDC |
| `network` | `"base"` | `"base"` or `"base-sepolia"` |
| `asset` | USDC Base contract | ERC-20 token address |
| `description` | `"API payment"` | Shown in wallet UI |
| `max_timeout_seconds` | `300` | Payment validity window |
| `enabled` | `True` | Set `False` to bypass (dev/test) |

## Graceful Degradation

If the Coinbase facilitator is unreachable, requests are allowed through automatically. Set `enabled=False` for local development.

## License

MIT — extracted from [Monad Mate Trust API](https://github.com/HankGrimm/monad-mate-trust-api). Built for EasyA × Consensus Miami 2026.
