"""
Core stake gate — framework-agnostic stake-gated access control.

Usage:
    gate = StakeGate(min_amounts={StakeType.DM: 0.5, StakeType.ROOM_ENTRY: 0.1})
    gate.validate(stake_type=StakeType.DM, amount=0.5, no_show_count=0)
    record = StakeRecord(user_id="0xABC", stake_type=StakeType.DM, amount=0.5)
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


class StakeType(str, enum.Enum):
    DM = "dm"
    ROOM_ENTRY = "room_entry"
    MEETUP_REQUEST = "meetup_request"
    PHOTO_UNLOCK = "photo_unlock"
    MEETUP_CONFIRM = "meetup_confirm"


class StakeStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REFUNDED = "refunded"
    SLASHED = "slashed"
    RELEASED = "released"
    DISPUTED = "disputed"


# Default minimum MON amounts per stake type
DEFAULT_MIN_AMOUNTS: dict[StakeType, float] = {
    StakeType.DM: 0.50,
    StakeType.ROOM_ENTRY: 0.10,
    StakeType.MEETUP_REQUEST: 1.00,
    StakeType.PHOTO_UNLOCK: 0.25,
    StakeType.MEETUP_CONFIRM: 1.00,
}

# No-show multiplier: each no-show increases required stake by 0.5×, max 3×
NO_SHOW_MULTIPLIER_STEP = 0.5
NO_SHOW_MAX_MULTIPLIER = 3.0


@dataclass
class StakeRecord:
    """Represents a single stake. Storage-agnostic (no ORM)."""
    user_id: str
    stake_type: StakeType
    amount_mon: float
    id: str = field(default_factory=lambda: str(uuid4()))
    status: StakeStatus = StakeStatus.PENDING
    room_id: Optional[str] = None
    reference_id: Optional[str] = None       # match_id, dm_id, etc.
    monad_tx_hash: Optional[str] = None      # EventLog tx hash
    monad_escrow_ref: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def activate(self) -> None:
        self.status = StakeStatus.ACTIVE
        self.updated_at = datetime.utcnow()

    def refund(self) -> None:
        self.status = StakeStatus.REFUNDED
        self.updated_at = datetime.utcnow()

    def slash(self) -> None:
        self.status = StakeStatus.SLASHED
        self.updated_at = datetime.utcnow()


class StakeGate:
    """
    Validates and manages stake requirements for any action type.

    Args:
        min_amounts:  Per-type minimum MON amounts. Falls back to DEFAULT_MIN_AMOUNTS.
        on_stake:     Optional callback(record: StakeRecord) called after stake creation.
        on_refund:    Optional callback(record: StakeRecord) after refund.
        on_slash:     Optional callback(record: StakeRecord, reason: str) after slash.
    """

    def __init__(
        self,
        min_amounts: Optional[dict] = None,
        on_stake=None,
        on_refund=None,
        on_slash=None,
    ):
        self.min_amounts = {**DEFAULT_MIN_AMOUNTS, **(min_amounts or {})}
        self.on_stake = on_stake
        self.on_refund = on_refund
        self.on_slash = on_slash

    def required_amount(
        self, stake_type: StakeType, no_show_count: int = 0
    ) -> float:
        """Return the required stake amount, applying no-show multiplier."""
        base = self.min_amounts.get(stake_type, 0.50)
        multiplier = min(
            1.0 + no_show_count * NO_SHOW_MULTIPLIER_STEP,
            NO_SHOW_MAX_MULTIPLIER,
        )
        return round(base * multiplier, 6)

    def validate(
        self,
        stake_type: StakeType,
        amount_mon: float,
        no_show_count: int = 0,
    ) -> tuple[bool, str]:
        """
        Check if an amount satisfies the stake requirement.

        Returns (True, "") or (False, error_message).
        """
        required = self.required_amount(stake_type, no_show_count)
        if amount_mon < required:
            return False, f"Minimum stake for {stake_type.value} is {required:.2f} MON (you sent {amount_mon:.2f})"
        return True, ""

    def create_stake(
        self,
        user_id: str,
        stake_type: StakeType,
        amount_mon: float,
        room_id: Optional[str] = None,
        reference_id: Optional[str] = None,
        no_show_count: int = 0,
    ) -> StakeRecord:
        """
        Create and activate a stake record.

        Raises ValueError if amount doesn't meet minimum.
        """
        valid, error = self.validate(stake_type, amount_mon, no_show_count)
        if not valid:
            raise ValueError(error)

        record = StakeRecord(
            user_id=user_id,
            stake_type=stake_type,
            amount_mon=amount_mon,
            room_id=room_id,
            reference_id=reference_id,
        )
        record.activate()

        if self.on_stake:
            self.on_stake(record)

        return record

    def refund_stake(self, record: StakeRecord) -> StakeRecord:
        """Mark stake as refunded and trigger callback."""
        record.refund()
        if self.on_refund:
            self.on_refund(record)
        return record

    def slash_stake(self, record: StakeRecord, reason: str) -> StakeRecord:
        """Mark stake as slashed and trigger callback."""
        record.slash()
        if self.on_slash:
            self.on_slash(record, reason)
        return record
