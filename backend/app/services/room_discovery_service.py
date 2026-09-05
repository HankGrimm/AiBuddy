import math
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models.room import Room
from ..models.persona import Persona, IntentMode


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def get_nearby_rooms(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float,
    intent_mode: Optional[str] = None,
) -> List[Room]:
    """Return active rooms within radius_km of (lat, lng), sorted by distance."""
    q = db.query(Room).filter(
        Room.is_active == True,
        Room.latitude != None,
        Room.longitude != None,
    )
    if intent_mode:
        q = q.filter(Room.intent_modes.contains([intent_mode]))

    rooms = q.all()

    in_radius = []
    for room in rooms:
        dist = _haversine_km(lat, lng, room.latitude, room.longitude)
        if dist <= radius_km:
            in_radius.append((dist, room))

    in_radius.sort(key=lambda x: x[0])
    return [room for _, room in in_radius]


def get_active_rooms(
    db: Session,
    type: Optional[str] = None,
    limit: int = 20,
) -> List[Room]:
    """Return rooms where starts_at <= now <= ends_at (or ends_at is None)."""
    now = datetime.utcnow()
    q = db.query(Room).filter(
        Room.is_active == True,
        Room.starts_at <= now,
    ).filter(
        (Room.ends_at == None) | (Room.ends_at >= now)
    )
    if type:
        q = q.filter(Room.type == type)
    return q.limit(limit).all()


def suggest_rooms_for_persona(
    db: Session,
    persona_id: str,
) -> List[Room]:
    """Return active rooms matching the persona's intent_mode."""
    persona = db.query(Persona).filter(
        Persona.id == persona_id,
        Persona.is_active == True,
    ).first()
    if not persona:
        return []

    intent_value = persona.intent_mode.value if persona.intent_mode else None
    if not intent_value:
        return db.query(Room).filter(Room.is_active == True).limit(20).all()

    rooms = db.query(Room).filter(Room.is_active == True).all()
    return [r for r in rooms if intent_value in (r.intent_modes or [])]
