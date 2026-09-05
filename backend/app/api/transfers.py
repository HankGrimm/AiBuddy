"""
Transfers API — MON gifting between users.
Refs #16
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.transfer import TransferCreate, TransferResponse
from ..services.transfer_service import TransferService

router = APIRouter(tags=["transfers"])


@router.post("/v1/transfers", response_model=TransferResponse, status_code=201)
async def create_transfer(
    payload: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = TransferService(db)
    return svc.create(current_user, payload)
