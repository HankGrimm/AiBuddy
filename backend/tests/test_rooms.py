import uuid
from datetime import datetime, timedelta

import pytest

from app.core.auth import create_access_token
from app.models.user import User
from app.models.room import Room, RoomType, RoomPrivacyLevel
from app.models.persona import Persona, IntentMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db, wallet: str = None) -> User:
    wallet = wallet or f"wallet-{uuid.uuid4().hex[:8]}"
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id), user.wallet_address)
    return {"Authorization": f"Bearer {token}"}


def _make_room(db, **kwargs) -> Room:
    defaults = dict(
        id=uuid.uuid4(),
        name="Test Room",
        type=RoomType.LOUNGE,
        privacy_level=RoomPrivacyLevel.PUBLIC,
        stake_required=0.0,
        intent_modes=[],
        is_active=True,
    )
    defaults.update(kwargs)
    room = Room(**defaults)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def _make_persona(db, user: User, **kwargs) -> Persona:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="TestPersona",
        intent_mode=IntentMode.SOCIAL,
        is_active=True,
    )
    defaults.update(kwargs)
    persona = Persona(**defaults)
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_list_rooms_empty(client):
    resp = client.get("/v1/rooms")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_room_requires_auth(client):
    resp = client.post("/v1/rooms", json={
        "name": "No Auth Room",
        "type": "lounge",
        "privacy_level": "public",
    })
    # HTTPBearer returns 403 when no credentials header is present
    assert resp.status_code in (401, 403)


def test_create_room_success(client, db):
    user = _make_user(db)
    headers = _auth_headers(user)
    payload = {
        "name": "My Room",
        "description": "A test room",
        "type": "lounge",
        "privacy_level": "public",
        "stake_required": 0.0,
        "intent_modes": ["social"],
    }
    resp = client.post("/v1/rooms", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Room"
    assert data["type"] == "lounge"
    assert data["is_active"] is True


def test_get_room_not_found(client):
    resp = client.get("/v1/rooms/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_join_room_no_stake_when_not_required(client, db):
    user = _make_user(db)
    persona = _make_persona(db, user)
    room = _make_room(db, stake_required=0.0)
    headers = _auth_headers(user)

    resp = client.post(
        f"/v1/rooms/{room.id}/join",
        json={"persona_id": str(persona.id)},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "joined"


def test_join_room_requires_stake_when_gated(client, db):
    user = _make_user(db)
    persona = _make_persona(db, user)
    room = _make_room(db, stake_required=5.0)
    headers = _auth_headers(user)

    # No stake_tx_hash provided -> should fail with 402
    resp = client.post(
        f"/v1/rooms/{room.id}/join",
        json={"persona_id": str(persona.id)},
        headers=headers,
    )
    assert resp.status_code == 402

    # With stake_tx_hash -> should succeed
    resp2 = client.post(
        f"/v1/rooms/{room.id}/join",
        json={"persona_id": str(persona.id), "stake_tx_hash": "fake-tx-hash"},
        headers=headers,
    )
    assert resp2.status_code == 200


def test_leave_room(client, db):
    user = _make_user(db)
    room = _make_room(db)
    persona = _make_persona(db, user, room_id=room.id)
    headers = _auth_headers(user)

    resp = client.post(
        f"/v1/rooms/{room.id}/leave",
        params={"persona_id": str(persona.id)},
        headers=headers,
    )
    assert resp.status_code == 204

    # Persona should no longer be in the room
    db.refresh(persona)
    assert persona.room_id is None


def test_get_members(client, db):
    user = _make_user(db)
    room = _make_room(db)
    persona = _make_persona(db, user, room_id=room.id)
    headers = _auth_headers(user)

    resp = client.get(f"/v1/rooms/{room.id}/members", headers=headers)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["id"] == str(persona.id)


def test_discover_rooms_by_location(client, db):
    # Room within radius (San Francisco area)
    room_near = _make_room(db, name="Near Room", latitude=37.7749, longitude=-122.4194)
    # Room outside radius (New York)
    _make_room(db, name="Far Room", latitude=40.7128, longitude=-74.0060)

    resp = client.get(
        "/v1/rooms/discover",
        params={"lat": 37.7750, "lng": -122.4180, "radius_km": 5.0},
    )
    assert resp.status_code == 200
    results = resp.json()
    ids = [r["id"] for r in results]
    assert str(room_near.id) in ids
    # Far Room (NYC) should not appear within 5 km of SF
    far_names = [r["name"] for r in results]
    assert "Far Room" not in far_names
