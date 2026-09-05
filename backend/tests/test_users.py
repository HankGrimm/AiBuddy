"""Tests for the User Identity domain (Sprint 1)."""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.models.user import User, PrivacyMode, VerificationLevel
from app.services.user_identity_service import _nonce_store


WALLET = "0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db, wallet: str = WALLET, email: str = None) -> User:
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet,
        email=email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id), user.wallet_address)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Challenge endpoint
# ---------------------------------------------------------------------------

def test_wallet_challenge_returns_nonce(client):
    """POST /v1/users/challenge must return a nonce and expiry timestamp."""
    resp = client.post("/v1/users/challenge", params={"wallet_address": WALLET})
    assert resp.status_code == 200
    data = resp.json()
    assert "nonce" in data
    assert "expires_at" in data
    assert len(data["nonce"]) == 64  # 32 bytes hex


def test_wallet_challenge_stores_different_nonces_per_wallet(client):
    """Each call for a different wallet gets its own nonce."""
    resp1 = client.post("/v1/users/challenge", params={"wallet_address": WALLET})
    wallet2 = "0x2546BcD3c84621e976D8185a91A922aE77ECEc30"
    resp2 = client.post("/v1/users/challenge", params={"wallet_address": wallet2})
    assert resp1.json()["nonce"] != resp2.json()["nonce"]


# ---------------------------------------------------------------------------
# Onboard — invalid nonce
# ---------------------------------------------------------------------------

def test_onboard_invalid_nonce_rejected(client):
    """Onboarding with a nonce that was never issued must be rejected."""
    resp = client.post("/v1/users/onboard", json={
        "wallet_address": WALLET,
        "signature": "fake_sig",
        "nonce": "0" * 64,
    })
    assert resp.status_code == 401


def test_onboard_wrong_nonce_rejected(client):
    """Onboarding with a mismatched nonce is rejected even if one was issued."""
    client.post("/v1/users/challenge", params={"wallet_address": WALLET})
    resp = client.post("/v1/users/onboard", json={
        "wallet_address": WALLET,
        "signature": "fake_sig",
        "nonce": "wrong_nonce",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Onboard — valid (mock signature verification)
# ---------------------------------------------------------------------------

def test_onboard_valid_creates_user(client):
    """Onboarding with a valid nonce + mocked-good signature creates a user and returns a token."""
    # Get a real nonce
    ch_resp = client.post("/v1/users/challenge", params={"wallet_address": WALLET})
    nonce = ch_resp.json()["nonce"]

    # Mock the signature verifier so we don't need a real Monad keypair
    with patch(
        "app.services.user_identity_service._verify_monad_signature",
        return_value=True,
    ):
        resp = client.post("/v1/users/onboard", json={
            "wallet_address": WALLET,
            "signature": "mocked_valid_sig",
            "nonce": nonce,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["wallet_address"] == WALLET


def test_onboard_valid_idempotent(client):
    """Onboarding the same wallet twice returns the same user (upsert)."""
    def _onboard():
        ch_resp = client.post("/v1/users/challenge", params={"wallet_address": WALLET})
        nonce = ch_resp.json()["nonce"]
        with patch(
            "app.services.user_identity_service._verify_monad_signature",
            return_value=True,
        ):
            return client.post("/v1/users/onboard", json={
                "wallet_address": WALLET,
                "signature": "mocked_sig",
                "nonce": nonce,
            })

    r1 = _onboard()
    r2 = _onboard()
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["user"]["id"] == r2.json()["user"]["id"]


def test_onboard_invalid_signature_rejected(client):
    """Real signature verification rejects a fake sig."""
    ch_resp = client.post("/v1/users/challenge", params={"wallet_address": WALLET})
    nonce = ch_resp.json()["nonce"]
    resp = client.post("/v1/users/onboard", json={
        "wallet_address": WALLET,
        "signature": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "nonce": nonce,
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /me endpoints
# ---------------------------------------------------------------------------

def test_get_me_requires_auth(client):
    """GET /v1/users/me without a token must return 403 (HTTPBearer returns 403)."""
    resp = client.get("/v1/users/me")
    assert resp.status_code in (401, 403)


def test_get_me_returns_user(client, db):
    user = _make_user(db)
    resp = client.get("/v1/users/me", headers=_auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["wallet_address"] == WALLET
    assert data["id"] == str(user.id)


def test_update_privacy_mode(client, db):
    """PATCH /v1/users/me can update privacy_mode."""
    user = _make_user(db)
    resp = client.patch(
        "/v1/users/me",
        json={"privacy_mode": "private"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["privacy_mode"] == "private"


def test_update_email(client, db):
    """PATCH /v1/users/me can update email."""
    user = _make_user(db)
    resp = client.patch(
        "/v1/users/me",
        json={"email": "test@example.com"},
        headers=_auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["wallet_address"] == WALLET
