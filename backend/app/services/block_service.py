from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import uuid

from ..models.block import Block


class BlockService:
    def __init__(self, db: Session):
        self.db = db

    def block(self, blocker_id: UUID, blocked_id: UUID) -> Block:
        existing = self.db.query(Block).filter(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id,
        ).first()
        if existing:
            return existing

        block = Block(
            id=uuid.uuid4(),
            blocker_id=blocker_id,
            blocked_id=blocked_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(block)
        self.db.commit()
        self.db.refresh(block)
        return block

    def unblock(self, blocker_id: UUID, blocked_id: UUID) -> None:
        self.db.query(Block).filter(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id,
        ).delete()
        self.db.commit()

    def is_blocked(self, user_a_id: UUID, user_b_id: UUID) -> bool:
        """Bidirectional check — returns True if either user has blocked the other."""
        count = self.db.query(Block).filter(
            (
                (Block.blocker_id == user_a_id) & (Block.blocked_id == user_b_id)
            ) | (
                (Block.blocker_id == user_b_id) & (Block.blocked_id == user_a_id)
            )
        ).count()
        return count > 0

    def get_blocked_ids(self, user_id: UUID) -> list[UUID]:
        rows = self.db.query(Block.blocked_id).filter(Block.blocker_id == user_id).all()
        return [row[0] for row in rows]
