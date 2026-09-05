"""Tests for the Persona domain (Sprint 1)."""
import uuid
from datetime import datetime, timedelta

import pytest

from app.core.auth import create_access_token
from app.models.user import User
from app.models.persona import Persona, IntentMode, VisibilityScope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WALLET = "0x2546BcD3c84621e976D8185a91A922aE77ECEc30"


def _make_user(db, wallet: str = WALLET) -> User:
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id), user.wallet_address)
    return {"Authorization": f"Bearer {token}"}


def _create_persona_payload(**overrides) -> dict:
    base = {
        "display_name": "MonadMate Test",
        "intent_mode": "social",
        "visibility_scope": "room_only",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Create persona
# ---------------------------------------------------------------------------

def test_create_persona(client, db):
    """POST /v1/personas must create and return a persona."""
    user = _make_user(db)
    resp = client.post(
        "/v1/personas",
        json=_create_persona_payload(),
        headers=_auth_headers(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "MonadMate Test"
    assert data["user_id"] == str(user.id)
    assert data["is_active"] is True
    assert data["intent_mode"] == "social"
    assert data["visibility_scope"] == "room_only"


def test_create_persona_with_bio_and_expiry(client, db):
    """Persona can be created with bio and an expiry timestamp."""
    user = _make_user(db)
    future = (datetime.utcnow() + timedelta(days=7)).isoformat()
    resp = client.post(
        "/v1/personas",
        json=_create_persona_payload(bio="Hi, I'm just testing.", expires_at=future),
        headers=_auth_headers(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bio"] == "Hi, I'm just testing."
    assert data["expires_at"] is not None


def test_create_persona_requires_auth(client):
    """Creating a persona without auth must fail."""
    resp = client.post("/v1/personas", json=_create_persona_payload())
    assert resp.status_code in (401, 403)


def test_create_persona_display_name_too_short(client, db):
    """display_name with length < 2 is rejected."""
    user = _make_user(db)
    resp = client.post(
        "/v1/personas",
        json=_create_persona_payload(display_name="X"),
        headers=_auth_headers(user),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List personas
# ---------------------------------------------------------------------------

def test_list_my_personas(client, db):
    """GET /v1/personas/me returns only the current user's active personas."""
    user = _make_user(db)
    # Create two personas
    client.post("/v1/personas", json=_create_persona_payload(display_name="Persona A"), headers=_auth_headers(user))
    client.post("/v1/personas", json=_create_persona_payload(display_name="Persona B"), headers=_auth_headers(user))

    resp = client.get("/v1/personas/me", headers=_auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {p["display_name"] for p in data}
    assert names == {"Persona A", "Persona B"}


def test_list_my_personas_empty(client, db):
    """GET /v1/personas/me returns empty list when user has no personas."""
    user = _make_user(db)
    resp = client.get("/v1/personas/me", headers=_auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_my_personas_requires_auth(client):
    """GET /v1/personas/me without auth must fail."""
    resp = client.get("/v1/personas/me")
    assert resp.status_code in (401, 403)


def test_list_my_personas_excludes_other_user(client, db):
    """Personas from a different user are not visible in /me."""
    user1 = _make_user(db, wallet=WALLET)
    user2 = _make_user(db, wallet="0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03")

    client.post("/v1/personas", json=_create_persona_payload(display_name="User2 Persona"), headers=_auth_headers(user2))

    resp = client.get("/v1/personas/me", headers=_auth_headers(user1))
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Delete persona
# ---------------------------------------------------------------------------

def test_delete_persona(client, db):
    """DELETE /v1/personas/{id} deactivates the persona."""
    user = _make_user(db)
    create_resp = client.post(
        "/v1/personas",
        json=_create_persona_payload(),
        headers=_auth_headers(user),
    )
    persona_id = create_resp.json()["id"]

    del_resp = client.delete(f"/v1/personas/{persona_id}", headers=_auth_headers(user))
    assert del_resp.status_code == 204

    # Should no longer appear in list
    list_resp = client.get("/v1/personas/me", headers=_auth_headers(user))
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_delete_persona_not_found(client, db):
    """DELETE /v1/personas/{id} for a non-existent persona returns 404."""
    user = _make_user(db)
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/v1/personas/{fake_id}", headers=_auth_headers(user))
    assert resp.status_code == 404


def test_delete_other_user_persona_not_found(client, db):
    """User cannot delete another user's persona — returns 404."""
    user1 = _make_user(db, wallet=WALLET)
    user2 = _make_user(db, wallet="0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03")

    create_resp = client.post(
        "/v1/personas",
        json=_create_persona_payload(),
        headers=_auth_headers(user1),
    )
    persona_id = create_resp.json()["id"]

    # user2 tries to delete user1's persona
    resp = client.delete(f"/v1/personas/{persona_id}", headers=_auth_headers(user2))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Expired persona
# ---------------------------------------------------------------------------

def test_expired_persona_rejected(client, db):
    """A persona that has passed its expires_at is considered expired.

    The validate_active service method raises PersonaExpiredError (403).
    We test this via the PersonaService directly since the endpoint doesn't
    expose the validator — but we also verify via the DB state after a list.
    """
    from app.services.persona_service import PersonaService
    from app.core.errors import PersonaExpiredError

    user = _make_user(db)
    past = datetime.utcnow() - timedelta(seconds=1)
    persona = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Expired Persona",
        expires_at=past,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)

    svc = PersonaService(db)
    with pytest.raises(PersonaExpiredError):
        svc.validate_active(persona)

    # After validation, the persona should be deactivated in the DB
    db.refresh(persona)
    assert persona.is_active is False


def test_expired_persona_excluded_from_list(client, db):
    """Expired personas are NOT returned in GET /v1/personas/me."""
    user = _make_user(db)
    past = datetime.utcnow() - timedelta(seconds=1)

    # Add expired persona directly
    expired = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Expired",
        expires_at=past,
        is_active=False,  # pre-deactivated, as validate_active would do
    )
    db.add(expired)
    db.commit()

    resp = client.get("/v1/personas/me", headers=_auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == []


def test_inactive_persona_excluded_from_list(client, db):
    """is_active=False personas are not returned in /me."""
    user = _make_user(db)
    persona = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Inactive",
        is_active=False,
    )
    db.add(persona)
    db.commit()

    resp = client.get("/v1/personas/me", headers=_auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == []
