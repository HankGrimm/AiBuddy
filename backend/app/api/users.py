from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.user import UserOnboard, UserResponse, UserUpdate, WalletAuthChallenge, WalletAuthToken
from ..services.user_identity_service import UserIdentityService

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("/challenge", response_model=WalletAuthChallenge)
async def get_wallet_challenge(wallet_address: str, db: Session = Depends(get_db)):
    """Issue a nonce challenge for wallet auth."""
    svc = UserIdentityService(db)
    return svc.create_challenge(wallet_address)


@router.post("/onboard", response_model=WalletAuthToken)
async def onboard_user(payload: UserOnboard, db: Session = Depends(get_db)):
    """Onboard a new user by verifying wallet signature."""
    svc = UserIdentityService(db)
    return svc.onboard(payload)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = UserIdentityService(db)
    return svc.update_user(current_user, payload)
