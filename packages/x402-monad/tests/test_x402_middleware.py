"""Tests for x402-monad: X402Config, require_x402_payment, exception handler."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from x402_monad import X402Config, require_x402_payment, X402PaymentRequired, x402_exception_handler
from x402_monad.middleware import _build_402_response, _verify_payment


# ---------------------------------------------------------------------------
# X402Config
# ---------------------------------------------------------------------------

def test_config_amount_micro():
    config = X402Config(pay_to="0xABC", amount_usdc=0.5)
    assert config.amount_micro == "500000"


def test_config_amount_micro_one_dollar():
    config = X402Config(pay_to="0xABC", amount_usdc=1.0)
    assert config.amount_micro == "1000000"


def test_config_defaults():
    config = X402Config(pay_to="0xABC")
    assert config.network == "base"
    assert config.enabled is True
    assert config.max_timeout_seconds == 300


# ---------------------------------------------------------------------------
# FastAPI integration tests
# ---------------------------------------------------------------------------

def make_app(config: X402Config) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(X402PaymentRequired, x402_exception_handler)

    @app.get("/protected", dependencies=[Depends(require_x402_payment(config))])
    async def protected():
        return {"ok": True}

    return app


def test_no_payment_header_returns_402():
    config = X402Config(pay_to="0xPAYTO", amount_usdc=0.5)
    client = TestClient(make_app(config), raise_server_exceptions=False)
    resp = client.get("/protected")
    assert resp.status_code == 402
    body = resp.json()
    assert body["x402Version"] == 1
    assert body["accepts"][0]["maxAmountRequired"] == "500000"
    assert body["accepts"][0]["payTo"] == "0xPAYTO"
    assert body["accepts"][0]["network"] == "base"


def test_disabled_config_bypasses_payment():
    config = X402Config(pay_to="0xPAYTO", enabled=False)
    client = TestClient(make_app(config))
    resp = client.get("/protected")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@patch("x402_monad.middleware._verify_payment", new_callable=AsyncMock)
def test_valid_payment_header_returns_200(mock_verify):
    mock_verify.return_value = True
    config = X402Config(pay_to="0xPAYTO", amount_usdc=0.5)
    client = TestClient(make_app(config))
    resp = client.get("/protected", headers={"X-Payment": "valid_payment_proof"})
    assert resp.status_code == 200


@patch("x402_monad.middleware._verify_payment", new_callable=AsyncMock)
def test_invalid_payment_header_returns_402(mock_verify):
    mock_verify.return_value = False
    config = X402Config(pay_to="0xPAYTO", amount_usdc=0.5)
    client = TestClient(make_app(config), raise_server_exceptions=False)
    resp = client.get("/protected", headers={"X-Payment": "invalid_proof"})
    assert resp.status_code == 402


# ---------------------------------------------------------------------------
# _verify_payment — facilitator interaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("x402_monad.middleware.httpx.AsyncClient")
async def test_verify_payment_returns_true_on_valid(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"isValid": True}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    from fastapi import Request
    from starlette.datastructures import URL
    mock_request = MagicMock(spec=Request)
    mock_request.url = URL("https://example.com/protected")

    config = X402Config(pay_to="0xABC", amount_usdc=0.5)
    result = await _verify_payment("payment_proof", mock_request, config)
    assert result is True


@pytest.mark.asyncio
@patch("x402_monad.middleware.httpx.AsyncClient")
async def test_verify_payment_graceful_on_timeout(mock_client_cls):
    import httpx
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    from fastapi import Request
    from starlette.datastructures import URL
    mock_request = MagicMock(spec=Request)
    mock_request.url = URL("https://example.com/protected")

    config = X402Config(pay_to="0xABC", amount_usdc=0.5)
    result = await _verify_payment("proof", mock_request, config)
    assert result is True  # graceful degradation


@pytest.mark.asyncio
@patch("x402_monad.middleware.httpx.AsyncClient")
async def test_verify_payment_returns_false_when_invalid(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"isValid": False, "invalidReason": "expired"}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    from fastapi import Request
    from starlette.datastructures import URL
    mock_request = MagicMock(spec=Request)
    mock_request.url = URL("https://example.com/protected")

    config = X402Config(pay_to="0xABC", amount_usdc=0.5)
    result = await _verify_payment("proof", mock_request, config)
    assert result is False
