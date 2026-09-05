from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.safety import (
    ReportCreate, ReportResponse, ReportResolve,
    BlockCreate, BlockResponse,
)
from ..services.safety_service import SafetyService

router = APIRouter(prefix="/v1/safety", tags=["safety"])


@router.post("/report", response_model=ReportResponse, status_code=201)
async def file_report(
    payload: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SafetyService(db)
    return svc.file_report(current_user, payload)


@router.post("/block", response_model=BlockResponse, status_code=201)
async def block_user(
    payload: BlockCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SafetyService(db)
    return svc.block_user(current_user, payload.blocked_user_id)


@router.get("/reports", response_model=List[ReportResponse])
async def get_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SafetyService(db)
    return svc.get_reports_for_user(current_user)


@router.post("/reports/{report_id}/resolve", response_model=ReportResponse)
async def resolve_report(
    report_id: UUID,
    payload: ReportResolve,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = SafetyService(db)
    return svc.resolve_report(current_user, report_id, payload)
