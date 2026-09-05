"""
Coverage for room_discovery_service — get_nearby_rooms, get_active_rooms,
suggest_rooms_for_persona.
"""
import uuid
from datetime import datetime, timedelta

import pytest

from app.models.room import Room, RoomType, RoomPrivacyLevel
from app.models.persona import Persona, IntentMode
from app.models.user import User
from app.services.room_discovery_service import (
    get_nearby_rooms,
    get_active_rooms,
    suggest_rooms_for_persona,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _room(db, name, lat=None, lng=None, intent_modes=None,
          starts_at=None, ends_at=None, is_active=True, type=RoomType.LOUNGE) -> Room:
    r = Room(
        id=uuid.uuid4(),
        name=name,
        type=type,
        privacy_level=RoomPrivacyLevel.PUBLIC,
        stake_required=0.0,
        intent_modes=intent_modes or [],
        latitude=lat,
        longitude=lng,
        is_active=is_active,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _user(db) -> User:
    u = User(id=uuid.uuid4(), wallet_address=f"w_{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(u)
    db.commit()
    return u


def _persona(db, user: User, intent_mode=IntentMode.SOCIAL) -> Persona:
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="TestP",
        intent_mode=intent_mode,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ── get_nearby_rooms ──────────────────────────────────────────────────────────

def test_nearby_room_within_radius_returned(db):
    # Miami Beach — two points ~50 m apart
    near = _room(db, "Near", lat=25.7617, lng=-80.1918)
    result = get_nearby_rooms(db, lat=25.7617, lng=-80.1918, radius_km=1.0)
    ids = [r.id for r in result]
    assert near.id in ids


def test_far_room_excluded(db):
    _room(db, "SF Room", lat=37.7749, lng=-122.4194)
    result = get_nearby_rooms(db, lat=25.7617, lng=-80.1918, radius_km=5.0)
    names = [r.name for r in result]
    assert "SF Room" not in names


def test_room_without_coordinates_excluded(db):
    _room(db, "No Coords")  # lat/lng are None
    result = get_nearby_rooms(db, lat=25.7617, lng=-80.1918, radius_km=5000.0)
    names = [r.name for r in result]
    assert "No Coords" not in names


def test_nearby_rooms_sorted_by_distance(db):
    close = _room(db, "Close", lat=25.7617, lng=-80.1918)
    medium = _room(db, "Medium", lat=25.7700, lng=-80.1918)  # ~0.9 km
    result = get_nearby_rooms(db, lat=25.7617, lng=-80.1918, radius_km=5.0)
    names = [r.name for r in result]
    assert names.index("Close") < names.index("Medium")


def test_nearby_rooms_filtered_by_intent_mode(db):
    dating_room = _room(db, "Dating Room", lat=25.7617, lng=-80.1918, intent_modes=["dating"])
    social_room = _room(db, "Social Room", lat=25.7617, lng=-80.1918, intent_modes=["social"])
    result = get_nearby_rooms(db, lat=25.7617, lng=-80.1918, radius_km=1.0, intent_mode="dating")
    ids = [r.id for r in result]
    assert dating_room.id in ids
    assert social_room.id not in ids


def test_inactive_room_excluded_from_nearby(db):
    _room(db, "Inactive", lat=25.7617, lng=-80.1918, is_active=False)
    result = get_nearby_rooms(db, lat=25.7617, lng=-80.1918, radius_km=1.0)
    names = [r.name for r in result]
    assert "Inactive" not in names


# ── get_active_rooms ──────────────────────────────────────────────────────────

def test_get_active_rooms_returns_current_rooms(db):
    now = datetime.utcnow()
    active = _room(db, "Active Event", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2))
    result = get_active_rooms(db)
    ids = [r.id for r in result]
    assert active.id in ids


def test_get_active_rooms_excludes_ended(db):
    now = datetime.utcnow()
    ended = _room(db, "Ended", starts_at=now - timedelta(hours=3), ends_at=now - timedelta(hours=1))
    result = get_active_rooms(db)
    ids = [r.id for r in result]
    assert ended.id not in ids


def test_get_active_rooms_excludes_not_started(db):
    now = datetime.utcnow()
    future = _room(db, "Future", starts_at=now + timedelta(hours=1))
    result = get_active_rooms(db)
    ids = [r.id for r in result]
    assert future.id not in ids


def test_get_active_rooms_no_ends_at_included(db):
    now = datetime.utcnow()
    forever = _room(db, "Forever", starts_at=now - timedelta(days=1))
    result = get_active_rooms(db)
    ids = [r.id for r in result]
    assert forever.id in ids


def test_get_active_rooms_filtered_by_type(db):
    now = datetime.utcnow()
    lounge = _room(db, "Lounge", starts_at=now - timedelta(hours=1), type=RoomType.LOUNGE)
    event = _room(db, "Event", starts_at=now - timedelta(hours=1), type=RoomType.EVENT)
    result = get_active_rooms(db, type=RoomType.LOUNGE)
    ids = [r.id for r in result]
    assert lounge.id in ids
    assert event.id not in ids


# ── suggest_rooms_for_persona ─────────────────────────────────────────────────

def test_suggest_rooms_for_persona_matches_intent(db):
    user = _user(db)
    persona = _persona(db, user, intent_mode=IntentMode.DATING)
    dating_room = _room(db, "Dating Room", intent_modes=["dating"])
    social_room = _room(db, "Social Room", intent_modes=["social"])

    result = suggest_rooms_for_persona(db, persona.id)
    ids = [r.id for r in result]
    assert dating_room.id in ids
    assert social_room.id not in ids


def test_suggest_rooms_persona_not_found_returns_empty(db):
    result = suggest_rooms_for_persona(db, uuid.uuid4())
    assert result == []


def test_suggest_rooms_inactive_persona_excluded(db):
    """Inactive persona returns empty list."""
    user = _user(db)
    p = Persona(
        id=uuid.uuid4(), user_id=user.id, display_name="Inactive",
        intent_mode=IntentMode.SOCIAL, is_active=False,
    )
    db.add(p)
    db.commit()
    result = suggest_rooms_for_persona(db, p.id)
    assert result == []
