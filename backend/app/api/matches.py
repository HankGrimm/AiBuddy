from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.match import MatchRequest, MatchResponse, MatchList
from ..schemas.message import MessageCreate, MessageResponse, MessageThread
from ..services.match_service import MatchService
from ..services.message_service import MessageService

router = APIRouter(tags=["matches"])


@router.post("/v1/matches/request", response_model=MatchResponse, status_code=201)
async def request_match(
    payload: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MatchService(db)
    return svc.request_match(current_user, payload)


@router.post("/v1/matches/{match_id}/accept", response_model=MatchResponse)
async def accept_match(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MatchService(db)
    return svc.accept(current_user, match_id)


@router.post("/v1/matches/{match_id}/reject", response_model=MatchResponse)
async def reject_match(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MatchService(db)
    return svc.reject(current_user, match_id)


@router.get("/v1/matches/me", response_model=MatchList)
async def my_matches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    svc = MatchService(db)
    return svc.get_user_matches(current_user, skip=skip, limit=limit)


# Messages
@router.post("/v1/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = MessageService(db)
    return svc.send(current_user, payload)


@router.get("/v1/messages/{match_id}", response_model=MessageThread)
async def get_messages(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    svc = MessageService(db)
    return svc.get_thread(current_user, match_id, skip=skip, limit=limit)
