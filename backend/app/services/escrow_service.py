from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import uuid

from ..models.escrow import Escrow, EscrowStatus, EscrowType
from ..models.user import User
from ..schemas.escrow import EscrowCreate
from ..core.errors import EscrowError


class EscrowService:
    def __init__(self, db: Session):
        self.db = db

    def create_meetup(self, user: User, payload: EscrowCreate) -> Escrow:
        escrow = Escrow(
            id=uuid.uuid4(),
            type=EscrowType.MEETUP,
            initiator_user_id=user.id,
            counterparty_user_id=payload.counterparty_user_id,
            amount_mon=payload.amount_mon,
            status=EscrowStatus.OPEN,
            confirm_deadline=payload.confirm_deadline,
        )
        self.db.add(escrow)
        self.db.commit()
        self.db.refresh(escrow)
        # Funds are held on-chain by the MonadMateEscrow contract (native MON).
        # TODO: anchor to Hedera HCS
        return escrow

    def confirm(self, user: User, escrow_id: UUID) -> Escrow:
        escrow = self._get_or_404(escrow_id)
        if escrow.initiator_user_id != user.id and escrow.counterparty_user_id != user.id:
            raise EscrowError("Not a party to this escrow")
        if escrow.status != EscrowStatus.OPEN:
            raise EscrowError("Escrow is not in open state")

        escrow.status = EscrowStatus.CONFIRMED
        escrow.resolved_at = datetime.utcnow()
        # On-chain MON settlement happens in the MonadMateEscrow contract.
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def dispute(self, user: User, escrow_id: UUID, reason: str) -> Escrow:
        escrow = self._get_or_404(escrow_id)
        if escrow.initiator_user_id != user.id and escrow.counterparty_user_id != user.id:
            raise EscrowError("Not a party to this escrow")
        escrow.status = EscrowStatus.DISPUTED
        escrow.dispute_reason = reason
        # TODO: trigger moderation queue
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def _get_or_404(self, escrow_id: UUID) -> Escrow:
        e = self.db.query(Escrow).filter(Escrow.id == escrow_id).first()
        if not e:
            from fastapi import HTTPException
            raise HTTPException(404, "Escrow not found")
        return e
