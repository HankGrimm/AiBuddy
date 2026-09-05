"""
Tests for StakeService and slashing policy (no-show path).
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from app.models.user import User, VerificationLevel, PrivacyMode
from app.models.stake import Stake, StakeStatus, StakeType
from app.schemas.stake import StakeCreate
from app.services.stake_service import StakeService
from app.services.slashing_policy_service import SlashingPolicyService
from app.core.errors import InsufficientStakeError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(db: Session, wallet: str = None) -> User:
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet or f"wallet_{uuid.uuid4().hex[:8]}",
        verification_level=VerificationLevel.WALLET,
        privacy_mode=PrivacyMode.SEMI_PRIVATE,
        age_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Minimum stake enforcement
# ---------------------------------------------------------------------------

def test_create_stake_dm_minimum_enforced(db: Session):
    """Stake below MIN_STAKE_DM_USDC (1.0) must raise InsufficientStakeError."""
    user = make_user(db)
    svc = StakeService(db)
    payload = StakeCreate(stake_type=StakeType.DM, amount_usdc=0.50)

    with pytest.raises(InsufficientStakeError):
        svc.create(user, payload)


def test_create_stake_dm_at_minimum_succeeds(db: Session):
    """Stake exactly at DM minimum should succeed."""
    user = make_user(db)
    svc = StakeService(db)
    payload = StakeCreate(stake_type=StakeType.DM, amount_usdc=1.0)

    stake = svc.create(user, payload)
    assert stake.status == StakeStatus.ACTIVE
    assert stake.amount_usdc == 1.0


def test_create_stake_meetup_minimum_enforced(db: Session):
    """Stake below MIN_STAKE_MEETUP_USDC (5.0) must raise InsufficientStakeError."""
    user = make_user(db)
    svc = StakeService(db)
    payload = StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=2.0)

    with pytest.raises(InsufficientStakeError):
        svc.create(user, payload)


def test_create_stake_meetup_at_minimum_succeeds(db: Session):
    """Stake exactly at meetup minimum should succeed."""
    user = make_user(db)
    svc = StakeService(db)
    payload = StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=5.0)

    stake = svc.create(user, payload)
    assert stake.status == StakeStatus.ACTIVE
    assert stake.stake_type == StakeType.REQUEST_MEETUP


# ---------------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------------

def test_refund_stake_changes_status(db: Session):
    """Refunding an active stake must flip status to REFUNDED and set resolved_at."""
    user = make_user(db)
    svc = StakeService(db)
    stake = svc.create(user, StakeCreate(stake_type=StakeType.DM, amount_usdc=1.0))

    refunded = svc.refund(user, stake.id)

    assert refunded.status == StakeStatus.REFUNDED
    assert refunded.resolved_at is not None


# ---------------------------------------------------------------------------
# Slashing
# ---------------------------------------------------------------------------

def test_slash_stake_records_reason(db: Session):
    """Slashing a stake must record status=SLASHED, slash_reason, and resolved_at."""
    user = make_user(db)
    svc = StakeService(db)
    stake = svc.create(user, StakeCreate(stake_type=StakeType.DM, amount_usdc=1.0))

    slashed = svc.slash(user, stake.id, reason="no-show: missed confirmed meetup")

    assert slashed.status == StakeStatus.SLASHED
    assert "no-show" in slashed.slash_reason
    assert slashed.resolved_at is not None


# ---------------------------------------------------------------------------
# Slashing policy — no-show
# ---------------------------------------------------------------------------

def test_slashing_policy_no_show(db: Session):
    """evaluate_no_show must return should_slash=True with full stake amount."""
    user = make_user(db)
    svc = StakeService(db)
    policy = SlashingPolicyService(db)

    stake = svc.create(user, StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=5.0))
    decision = policy.evaluate_no_show(stake)

    assert decision.should_slash is True
    assert decision.slash_amount_usdc == stake.amount_usdc
    assert decision.penalty_pct == 1.0
    assert "no-show" in decision.reason.lower()


def test_slashing_policy_no_show_inactive_stake(db: Session):
    """evaluate_no_show on an already-slashed stake must return should_slash=False."""
    user = make_user(db)
    svc = StakeService(db)
    policy = SlashingPolicyService(db)

    stake = svc.create(user, StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=5.0))
    svc.slash(user, stake.id, reason="no-show: prior event")
    db.refresh(stake)

    decision = policy.evaluate_no_show(stake)
    assert decision.should_slash is False


def test_slashing_policy_three_no_shows_suspends_dm(db: Session):
    """After 3 no-show slashes should_suspend_dm must return True."""
    user = make_user(db)
    svc = StakeService(db)
    policy = SlashingPolicyService(db)

    # Before any violations
    assert policy.should_suspend_dm(user.id) is False

    for i in range(3):
        s = svc.create(
            user,
            StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=5.0),
        )
        svc.slash(user, s.id, reason="no-show: missed meetup")

    assert policy.should_suspend_dm(user.id) is True


def test_stake_multiplier_increases_with_no_shows(db: Session):
    """get_stake_multiplier must increment by 0.5 per no-show, clamped at 3.0."""
    user = make_user(db)
    svc = StakeService(db)
    policy = SlashingPolicyService(db)

    # 0 no-shows → multiplier 1.0
    assert policy.get_stake_multiplier(user.id) == 1.0

    # 1 no-show → multiplier 1.5
    s = svc.create(user, StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=5.0))
    svc.slash(user, s.id, reason="no-show: missed meetup")
    assert policy.get_stake_multiplier(user.id) == 1.5

    # 2 no-shows → multiplier 2.0
    s2 = svc.create(user, StakeCreate(stake_type=StakeType.REQUEST_MEETUP, amount_usdc=5.0))
    svc.slash(user, s2.id, reason="no-show: missed meetup")
    assert policy.get_stake_multiplier(user.id) == 2.0
