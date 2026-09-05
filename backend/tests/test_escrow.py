"""
Tests for EscrowService and related slashing-policy (harassment / false-report) paths.
"""
import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.user import User, VerificationLevel, PrivacyMode
from app.models.stake import Stake, StakeStatus, StakeType
from app.models.report import Report, ReportType, ReportStatus
from app.schemas.escrow import EscrowCreate
from app.schemas.stake import StakeCreate
from app.models.escrow import EscrowStatus, EscrowType
from app.services.escrow_service import EscrowService
from app.services.stake_service import StakeService
from app.services.slashing_policy_service import SlashingPolicyService
from app.core.errors import EscrowError


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


def make_report(
    db: Session,
    reporter: User,
    reported: User,
    report_type: ReportType = ReportType.HARASSMENT,
    description: str = "User was aggressive and threatening during chat session",
) -> Report:
    report = Report(
        id=uuid.uuid4(),
        reporter_id=reporter.id,
        reported_user_id=reported.id,
        report_type=report_type,
        description=description,
        status=ReportStatus.PENDING,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# ---------------------------------------------------------------------------
# Escrow creation
# ---------------------------------------------------------------------------

def test_create_meetup_escrow(db: Session):
    """Creating a meetup escrow must persist it with status OPEN and correct amounts."""
    initiator = make_user(db)
    counterparty = make_user(db)
    svc = EscrowService(db)

    payload = EscrowCreate(
        type=EscrowType.MEETUP,
        counterparty_user_id=counterparty.id,
        amount_usdc=10.0,
        confirm_deadline=datetime.utcnow() + timedelta(days=3),
    )
    escrow = svc.create_meetup(initiator, payload)

    assert escrow.id is not None
    assert escrow.status == EscrowStatus.OPEN
    assert escrow.amount_usdc == 10.0
    assert escrow.initiator_user_id == initiator.id
    assert escrow.counterparty_user_id == counterparty.id
    assert escrow.type == EscrowType.MEETUP


def test_create_meetup_escrow_persisted(db: Session):
    """Escrow should survive a DB re-query (confirming it was committed)."""
    from app.models.escrow import Escrow

    initiator = make_user(db)
    counterparty = make_user(db)
    svc = EscrowService(db)

    payload = EscrowCreate(
        type=EscrowType.MEETUP,
        counterparty_user_id=counterparty.id,
        amount_usdc=7.5,
    )
    escrow = svc.create_meetup(initiator, payload)
    eid = escrow.id

    fetched = db.query(Escrow).filter(Escrow.id == eid).first()
    assert fetched is not None
    assert fetched.amount_usdc == 7.5


# ---------------------------------------------------------------------------
# Escrow confirmation
# ---------------------------------------------------------------------------

def test_confirm_escrow_by_counterparty(db: Session):
    """Counterparty confirming the escrow must flip status to CONFIRMED."""
    initiator = make_user(db)
    counterparty = make_user(db)
    svc = EscrowService(db)

    escrow = svc.create_meetup(
        initiator,
        EscrowCreate(
            type=EscrowType.MEETUP,
            counterparty_user_id=counterparty.id,
            amount_usdc=5.0,
        ),
    )

    confirmed = svc.confirm(counterparty, escrow.id)

    assert confirmed.status == EscrowStatus.CONFIRMED
    assert confirmed.resolved_at is not None


def test_confirm_escrow_by_initiator(db: Session):
    """Initiator can also confirm the escrow."""
    initiator = make_user(db)
    counterparty = make_user(db)
    svc = EscrowService(db)

    escrow = svc.create_meetup(
        initiator,
        EscrowCreate(
            type=EscrowType.MEETUP,
            counterparty_user_id=counterparty.id,
            amount_usdc=5.0,
        ),
    )
    confirmed = svc.confirm(initiator, escrow.id)
    assert confirmed.status == EscrowStatus.CONFIRMED


def test_confirm_escrow_by_stranger_rejected(db: Session):
    """A user unrelated to the escrow cannot confirm it."""
    initiator = make_user(db)
    counterparty = make_user(db)
    stranger = make_user(db)
    svc = EscrowService(db)

    escrow = svc.create_meetup(
        initiator,
        EscrowCreate(
            type=EscrowType.MEETUP,
            counterparty_user_id=counterparty.id,
            amount_usdc=5.0,
        ),
    )

    with pytest.raises(EscrowError):
        svc.confirm(stranger, escrow.id)


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------

def test_dispute_escrow_records_reason(db: Session):
    """Disputing an escrow must record status=DISPUTED and preserve the reason."""
    initiator = make_user(db)
    counterparty = make_user(db)
    svc = EscrowService(db)

    escrow = svc.create_meetup(
        initiator,
        EscrowCreate(
            type=EscrowType.MEETUP,
            counterparty_user_id=counterparty.id,
            amount_usdc=8.0,
        ),
    )

    dispute_reason = "Counterparty did not arrive at the agreed location and time."
    disputed = svc.dispute(initiator, escrow.id, reason=dispute_reason)

    assert disputed.status == EscrowStatus.DISPUTED
    assert disputed.dispute_reason == dispute_reason


def test_dispute_escrow_by_stranger_rejected(db: Session):
    """A user unrelated to the escrow cannot raise a dispute."""
    initiator = make_user(db)
    counterparty = make_user(db)
    stranger = make_user(db)
    svc = EscrowService(db)

    escrow = svc.create_meetup(
        initiator,
        EscrowCreate(
            type=EscrowType.MEETUP,
            counterparty_user_id=counterparty.id,
            amount_usdc=5.0,
        ),
    )

    with pytest.raises(EscrowError):
        svc.dispute(stranger, escrow.id, reason="Trying to cheat the system here.")


# ---------------------------------------------------------------------------
# Slashing policy — harassment
# ---------------------------------------------------------------------------

def test_slashing_policy_harassment(db: Session):
    """evaluate_harassment on a confirmed harassment report must slash full stake."""
    reporter = make_user(db)
    offender = make_user(db)
    stake_svc = StakeService(db)
    policy = SlashingPolicyService(db)

    stake = stake_svc.create(
        offender,
        StakeCreate(stake_type=StakeType.DM, amount_usdc=2.0),
    )
    report = make_report(db, reporter, offender, ReportType.HARASSMENT)

    decision = policy.evaluate_harassment(report, stake)

    assert decision.should_slash is True
    assert decision.slash_amount_usdc == stake.amount_usdc
    assert decision.penalty_pct == 1.0


# ---------------------------------------------------------------------------
# Slashing policy — false report
# ---------------------------------------------------------------------------

def test_slashing_policy_false_report(db: Session):
    """evaluate_false_report must return should_slash=True with 50 % penalty."""
    reporter = make_user(db)
    victim = make_user(db)
    policy = SlashingPolicyService(db)

    report = make_report(
        db,
        reporter,
        victim,
        report_type=ReportType.FALSE_REPORTING,
        description="Reporter fabricated a harassment claim.",
    )

    decision = policy.evaluate_false_report(report)

    assert decision.should_slash is True
    assert decision.penalty_pct == 0.5
