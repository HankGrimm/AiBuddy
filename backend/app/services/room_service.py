from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
import uuid
import math

from ..models.room import Room
from ..models.persona import Persona
from ..models.user import User
from ..schemas.room import RoomCreate, RoomJoin
from ..core.errors import RoomNotFoundError, RoomAccessDeniedError, StakeRequiredError


class RoomService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, payload: RoomCreate) -> Room:
        room = Room(
            id=uuid.uuid4(),
            host_user_id=user.id,
            name=payload.name,
            description=payload.description,
            type=payload.type,
            location=payload.location,
            latitude=payload.latitude,
            longitude=payload.longitude,
            geofence_radius_meters=payload.geofence_radius_meters,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            privacy_level=payload.privacy_level,
            stake_required=payload.stake_required,
            intent_modes=[m.value for m in payload.intent_modes],
        )
        self.db.add(room)
        self.db.commit()
        self.db.refresh(room)
        return room

    def get_or_404(self, room_id: UUID) -> Room:
        room = self.db.query(Room).filter(Room.id == room_id, Room.is_active == True).first()
        if not room:
            raise RoomNotFoundError()
        return room

    def list_rooms(
        self,
        type: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius_km: Optional[float] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Room]:
        q = self.db.query(Room).filter(Room.is_active == True)
        if type:
            q = q.filter(Room.type == type)
        rooms = q.offset(skip).limit(limit).all()

        if lat and lng and radius_km:
            rooms = [r for r in rooms if self._within_radius(r, lat, lng, radius_km)]
        return rooms

    def join(self, user: User, room_id: UUID, payload: RoomJoin) -> dict:
        room = self.get_or_404(room_id)
        if room.stake_required > 0 and not payload.stake_tx_hash:
            raise StakeRequiredError(room.stake_required, "join this room")

        # Assign persona to room
        persona = self.db.query(Persona).filter(
            Persona.id == payload.persona_id,
            Persona.user_id == user.id,
            Persona.is_active == True,
        ).first()
        if not persona:
            raise RoomAccessDeniedError("Persona not found or inactive")

        persona.room_id = room_id
        self.db.commit()
        return {"status": "joined", "room_id": str(room_id)}

    def leave(self, user: User, room_id: UUID, persona_id: UUID):
        persona = self.db.query(Persona).filter(
            Persona.id == persona_id,
            Persona.user_id == user.id,
            Persona.room_id == room_id,
        ).first()
        if persona:
            persona.room_id = None
            self.db.commit()

    def get_members(self, room_id: UUID) -> List[Persona]:
        self.get_or_404(room_id)
        return self.db.query(Persona).filter(
            Persona.room_id == room_id, Persona.is_active == True
        ).all()

    def _within_radius(self, room: Room, lat: float, lng: float, radius_km: float) -> bool:
        if room.latitude is None or room.longitude is None:
            return False
        dlat = math.radians(room.latitude - lat)
        dlng = math.radians(room.longitude - lng)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(room.latitude)) * math.sin(dlng/2)**2
        return 6371 * 2 * math.asin(math.sqrt(a)) <= radius_km
