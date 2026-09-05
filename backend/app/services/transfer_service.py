"""
Transfer service — MON gifting between users.
Refs #16
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models.user import User
from ..models.transfer import Transfer, TransferStatus
from ..schemas.transfer import TransferCreate


class TransferService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, sender: User, payload: TransferCreate) -> Transfer:
        # Lookup recipient by wallet address
        recipient = (
            self.db.query(User)
            .filter(User.wallet_address == payload.recipient_wallet)
            .first()
        )
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient wallet not found")

        if recipient.id == sender.id:
            raise HTTPException(status_code=400, detail="Cannot transfer MON to yourself")

        transfer = Transfer(
            sender_id=sender.id,
            recipient_id=recipient.id,
            amount_mon=payload.amount_mon,
            message=payload.message,
            status=TransferStatus.PENDING,
        )
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def get_sent(self, user_id, limit: int = 20, offset: int = 0):
        return (
            self.db.query(Transfer)
            .filter(Transfer.sender_id == user_id)
            .order_by(Transfer.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_received(self, user_id, limit: int = 20, offset: int = 0):
        return (
            self.db.query(Transfer)
            .filter(Transfer.recipient_id == user_id)
            .order_by(Transfer.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
