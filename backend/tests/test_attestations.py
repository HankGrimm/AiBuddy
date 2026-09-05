"""
Sprint 4 — Meetup Attestation tests
Covers: QR initiation, dual confirmation, wrong-token rejection,
GPS proximity checks, escrow release, and reputation update on confirm.
"""
import uuid
import pytest
from datetime import datetime, timedelta

from app.models.attestation import MeetupAttestation, AttestationStatus, AttestationMethod
from app.models.escrow import Escrow, EscrowStatus, EscrowType
from app.models.match import Match, MatchStatus, ConsentState
from app.models.persona import Persona
from app.models.reputation import ReputationScore
from app.models.user import User, VerificationLevel, PrivacyMode
from app.schemas.attestation import AttestationInitiate, AttestationConfirm
from app.services.meetup_attestation_service import MeetupAttestationService
from app.services.proximity_verification_service import ProximityVerificationService


# ------------------------------------------------------------------ fixtures
def make_user(db) -> User:
    u = User(
        id=uuid.uuid4(),
        wallet_address=f"wallet_{uuid.uuid4().hex[:8]}",
        verification_level=VerificationLevel.WALLET,
        privacy_mode=PrivacyMode.SEMI_PRIVATE,
    )
    db.add(u)
    db.commit()
    return u


def make_persona(db, user: User) -> Persona:
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Tester",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(p)
    db.commit()
    return p


def make_match(db, persona_a: Persona, persona_b: Persona) -> Match:
    m = Match(
        id=uuid.uuid4(),
        requester_persona_id=persona_a.id,
        target_persona_id=persona_b.id,
        status=MatchStatus.ACCEPTED,
        consent_state=ConsentState.GRANTED,
    )
    db.add(m)
    db.commit()
    return m


def make_escrow(db, user_a: User, user_b: User) -> Escrow:
    e = Escrow(
        id=uuid.uuid4(),
        type=EscrowType.MEETUP,
        initiator_user_id=user_a.id,
        counterparty_user_id=user_b.id,
        amount_usdc=5.0,
        status=EscrowStatus.OPEN,
    )
    db.add(e)
    db.commit()
    return e


# ------------------------------------------------------------------ QR token generation
def test_initiate_qr_attestation_generates_token(db):
    user_a = make_user(db)
    user_b = make_user(db)
    persona_a = make_persona(db, user_a)
    persona_b = make_persona(db, user_b)
    match = make_match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    payload = AttestationInitiate(match_id=match.id, method=AttestationMethod.QR_CODE)
    attestation = svc.initiate(user_a, payload)

    assert attestation.status == AttestationStatus.INITIATED
    assert attestation.token is not None
    assert len(attestation.token) > 0
    assert attestation.method == AttestationMethod.QR_CODE


# ------------------------------------------------------------------ dual QR confirmation
def test_confirm_qr_attestation_both_sides(db):
    user_a = make_user(db)
    user_b = make_user(db)
    persona_a = make_persona(db, user_a)
    persona_b = make_persona(db, user_b)
    match = make_match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    init_payload = AttestationInitiate(match_id=match.id, method=AttestationMethod.QR_CODE)
    attestation = svc.initiate(user_a, init_payload)
    token = attestation.token

    # Initiator confirms
    attestation = svc.confirm(user_a, attestation.id, AttestationConfirm(token=token))
    assert attestation.initiator_confirmed is True
    assert attestation.status == AttestationStatus.PENDING_CONFIRM

    # Counterparty confirms
    attestation = svc.confirm(user_b, attestation.id, AttestationConfirm(token=token))
    assert attestation.counterparty_confirmed is True
    assert attestation.status == AttestationStatus.CONFIRMED
    assert attestation.confirmed_at is not None


# ------------------------------------------------------------------ wrong token rejection
def test_confirm_wrong_token_rejected(db):
    from app.core.errors import AttestationError

    user_a = make_user(db)
    user_b = make_user(db)
    persona_a = make_persona(db, user_a)
    persona_b = make_persona(db, user_b)
    match = make_match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    attestation = svc.initiate(
        user_a, AttestationInitiate(match_id=match.id, method=AttestationMethod.QR_CODE)
    )

    with pytest.raises(AttestationError):
        svc.confirm(user_b, attestation.id, AttestationConfirm(token="WRONG_TOKEN_XYZ"))


# ------------------------------------------------------------------ GPS distance checks
def test_gps_too_far_rejected():
    svc = ProximityVerificationService()
    # ~200 m apart
    ok = svc.verify_gps(37.7749, -122.4194, 37.7767, -122.4194, max_meters=100)
    assert ok is False


def test_gps_close_enough_accepted():
    svc = ProximityVerificationService()
    # ~50 m apart
    ok = svc.verify_gps(37.7749, -122.4194, 37.77535, -122.4194, max_meters=100)
    assert ok is True


# ------------------------------------------------------------------ escrow released on confirm
def test_confirmed_attestation_releases_escrow(db):
    user_a = make_user(db)
    user_b = make_user(db)
    persona_a = make_persona(db, user_a)
    persona_b = make_persona(db, user_b)
    match = make_match(db, persona_a, persona_b)
    escrow = make_escrow(db, user_a, user_b)

    svc = MeetupAttestationService(db)
    attestation = svc.initiate(
        user_a,
        AttestationInitiate(
            match_id=match.id,
            method=AttestationMethod.QR_CODE,
            escrow_id=escrow.id,
        ),
    )
    token = attestation.token

    svc.confirm(user_a, attestation.id, AttestationConfirm(token=token))
    svc.confirm(user_b, attestation.id, AttestationConfirm(token=token))

    db.refresh(escrow)
    assert escrow.status == EscrowStatus.CONFIRMED


# ------------------------------------------------------------------ reputation updated on confirm
def test_confirmed_attestation_updates_reputation(db):
    user_a = make_user(db)
    user_b = make_user(db)
    persona_a = make_persona(db, user_a)
    persona_b = make_persona(db, user_b)
    match = make_match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    attestation = svc.initiate(
        user_a, AttestationInitiate(match_id=match.id, method=AttestationMethod.QR_CODE)
    )
    token = attestation.token

    svc.confirm(user_a, attestation.id, AttestationConfirm(token=token))
    svc.confirm(user_b, attestation.id, AttestationConfirm(token=token))

    score_a = db.query(ReputationScore).filter(ReputationScore.user_id == user_a.id).first()
    score_b = db.query(ReputationScore).filter(ReputationScore.user_id == user_b.id).first()

    assert score_a is not None
    assert score_b is not None
    # meetup_completion_score should have increased above the 50 default
    assert score_a.meetup_completion_score > 50.0
    assert score_b.meetup_completion_score > 50.0
