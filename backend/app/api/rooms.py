from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.room import RoomCreate, RoomResponse, RoomJoin
from ..schemas.persona import PersonaResponse
from ..services.room_service import RoomService
from ..services import room_discovery_service

router = APIRouter(prefix="/v1/rooms", tags=["rooms"])


@router.post("", response_model=RoomResponse, status_code=201)
async def create_room(
    payload: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = RoomService(db)
    return svc.create(current_user, payload)


@router.get("", response_model=List[RoomResponse])
async def list_rooms(
    type: Optional[str] = Query(None),
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    radius_km: Optional[float] = Query(None),
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    svc = RoomService(db)
    return svc.list_rooms(type=type, lat=latitude, lng=longitude, radius_km=radius_km, skip=skip, limit=limit)


@router.get("/discover", response_model=List[RoomResponse])
async def discover_rooms(
    lat: float = Query(..., description="Latitude of the requester"),
    lng: float = Query(..., description="Longitude of the requester"),
    radius_km: float = Query(10.0, gt=0, description="Search radius in kilometres"),
    intent_mode: Optional[str] = Query(None, description="Filter by intent mode"),
    db: Session = Depends(get_db),
):
    return room_discovery_service.get_nearby_rooms(
        db=db,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        intent_mode=intent_mode,
    )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: UUID, db: Session = Depends(get_db)):
    svc = RoomService(db)
    return svc.get_or_404(room_id)


@router.post("/{room_id}/join", status_code=200)
async def join_room(
    room_id: UUID,
    payload: RoomJoin,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = RoomService(db)
    return svc.join(current_user, room_id, payload)


@router.post("/{room_id}/leave", status_code=204)
async def leave_room(
    room_id: UUID,
    persona_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = RoomService(db)
    svc.leave(current_user, room_id, persona_id)


@router.get("/{room_id}/members", response_model=List[PersonaResponse])
async def get_room_members(
    room_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = RoomService(db)
    return svc.get_members(room_id)
