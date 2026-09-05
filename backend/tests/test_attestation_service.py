"""
Targeted tests for MeetupAttestationService — coverage push to 90%+.

Focuses on the specific missing lines identified by coverage analysis:
  - Line 46:     expired attestation raises AttestationError
  - Lines 54-57: GPS validation branch (too far / within range)
  - Lines 80-81: verify_proximity delegates to initiate with GPS_CHECKIN
  - Line 84:     get_user_attestations queries both initiator and counterparty
  - Line 116:    _on_confirmed sets hcs_message_id when HCS returns a value
  - Lines 121-122: _on_confirmed updates reputation for both parties
  - Lines 126-132: _haversine full math path + None-coord early-exit
"""
import uuid
import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.models.attestation import MeetupAttestation, AttestationStatus, AttestationMethod
from app.models.escrow import Escrow, EscrowStatus, EscrowType
from app.models.match import Match, MatchStatus, ConsentState
from app.models.persona import Persona
from app.models.reputation import ReputationScore
from app.models.user import User, VerificationLevel, PrivacyMode
from app.schemas.attestation import AttestationInitiate, AttestationConfirm
from app.services.meetup_attestation_service import MeetupAttestationService
from app.core.errors import AttestationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(db) -> User:
    u = User(
        id=uuid.uuid4(),
        wallet_address=f"w_{uuid.uuid4().hex[:8]}",
        verification_level=VerificationLevel.WALLET,
        privacy_mode=PrivacyMode.SEMI_PRIVATE,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _persona(db, user: User) -> Persona:
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="TestUser",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(p)
    db.commit()
    return p


def _match(db, persona_a: Persona, persona_b: Persona) -> Match:
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


def _escrow(db, user_a: User, user_b: User) -> Escrow:
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


def _make_confirmed_attestation(db, svc, user_a, user_b, match, **kwargs):
    """
    Convenience: create + fully confirm a QR attestation.
    Extra kwargs forwarded to AttestationInitiate.
    """
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.QR_CODE,
        **kwargs,
    ))
    token = att.token
    svc.confirm(user_a, att.id, AttestationConfirm(token=token))
    svc.confirm(user_b, att.id, AttestationConfirm(token=token))
    db.refresh(att)
    return att


# ---------------------------------------------------------------------------
# initiate — token generation
# ---------------------------------------------------------------------------

def test_initiate_qr_code_generates_token(db):
    """QR_CODE method must produce a non-empty token (line 21-23)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.QR_CODE,
    ))

    assert att.token is not None
    assert len(att.token) > 0


def test_initiate_ble_proximity_generates_token(db):
    """BLE_PROXIMITY method also generates a token."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.BLE_PROXIMITY,
    ))

    assert att.token is not None


def test_initiate_mutual_confirmation_has_no_token(db):
    """MUTUAL_CONFIRMATION must not generate a token (else branch of line 21-23)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.MUTUAL_CONFIRMATION,
    ))

    assert att.token is None


# ---------------------------------------------------------------------------
# confirm — expired attestation (line 46)
# ---------------------------------------------------------------------------

def test_confirm_expired_attestation_raises(db):
    """Confirming an EXPIRED attestation must raise AttestationError (line 46)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.MUTUAL_CONFIRMATION,
    ))

    # Manually expire the attestation
    att.status = AttestationStatus.EXPIRED
    db.commit()

    with pytest.raises(AttestationError, match="expired"):
        svc.confirm(user_b, att.id, AttestationConfirm())


# ---------------------------------------------------------------------------
# confirm — GPS validation branch (lines 54-57)
# ---------------------------------------------------------------------------

def test_confirm_gps_too_far_raises(db):
    """GPS_CHECKIN confirm where payload coords are >100 m away raises AttestationError (lines 54-57)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    # Attestation anchored at (37.7749, -122.4194)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.GPS_CHECKIN,
        latitude=37.7749,
        longitude=-122.4194,
    ))

    # Confirming ~200 m away — should be rejected
    with pytest.raises(AttestationError, match="100m"):
        svc.confirm(user_b, att.id, AttestationConfirm(
            latitude=37.7767,
            longitude=-122.4194,
        ))


def test_confirm_gps_within_range_passes(db):
    """GPS_CHECKIN confirm where payload coords are ≤100 m succeeds (lines 53-57, happy path)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.GPS_CHECKIN,
        latitude=37.7749,
        longitude=-122.4194,
    ))

    # ~50 m away — should pass
    result = svc.confirm(user_b, att.id, AttestationConfirm(
        latitude=37.77535,
        longitude=-122.4194,
    ))
    assert result.status in (AttestationStatus.PENDING_CONFIRM, AttestationStatus.CONFIRMED)


# ---------------------------------------------------------------------------
# confirm — one-sided then both-sided (lines 60-73)
# ---------------------------------------------------------------------------

def test_confirm_by_initiator_sets_pending(db):
    """Initiator confirming alone → initiator_confirmed=True, status=PENDING_CONFIRM."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.QR_CODE,
    ))

    result = svc.confirm(user_a, att.id, AttestationConfirm(token=att.token))

    assert result.initiator_confirmed is True
    assert result.status == AttestationStatus.PENDING_CONFIRM


def test_confirm_by_counterparty_after_initiator_triggers_confirmed(db):
    """Both sides confirming → status=CONFIRMED, confirmed_at set."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.QR_CODE,
    ))
    token = att.token

    svc.confirm(user_a, att.id, AttestationConfirm(token=token))
    result = svc.confirm(user_b, att.id, AttestationConfirm(token=token))

    assert result.counterparty_confirmed is True
    assert result.status == AttestationStatus.CONFIRMED
    assert result.confirmed_at is not None


# ---------------------------------------------------------------------------
# verify_proximity (lines 80-81)
# ---------------------------------------------------------------------------

def test_verify_proximity_delegates_to_initiate_with_gps_checkin(db):
    """verify_proximity must override method to GPS_CHECKIN and call initiate (lines 80-81)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    payload = AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.MUTUAL_CONFIRMATION,  # will be overridden
        latitude=37.7749,
        longitude=-122.4194,
    )
    att = svc.verify_proximity(user_a, payload)

    assert att.method == AttestationMethod.GPS_CHECKIN
    assert att.status == AttestationStatus.INITIATED
    assert att.latitude == 37.7749


# ---------------------------------------------------------------------------
# get_user_attestations (line 84)
# ---------------------------------------------------------------------------

def test_get_user_attestations_returns_for_initiator_and_counterparty(db):
    """get_user_attestations returns attestations where user is initiator OR counterparty (line 84)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    user_c = _user(db)
    persona_c = _persona(db, user_c)
    match_ab = _match(db, persona_a, persona_b)
    match_bc = _match(db, persona_b, persona_c)

    svc = MeetupAttestationService(db)

    # user_b initiates against user_c
    att1 = svc.initiate(user_b, AttestationInitiate(
        match_id=match_bc.id,
        method=AttestationMethod.QR_CODE,
    ))
    # user_a initiates, then user_b counter-confirms (making user_b counterparty)
    att2 = svc.initiate(user_a, AttestationInitiate(
        match_id=match_ab.id,
        method=AttestationMethod.QR_CODE,
    ))
    svc.confirm(user_a, att2.id, AttestationConfirm(token=att2.token))
    svc.confirm(user_b, att2.id, AttestationConfirm(token=att2.token))

    results = svc.get_user_attestations(user_b.id)
    result_ids = {r.id for r in results}

    assert att1.id in result_ids   # user_b is initiator
    assert att2.id in result_ids   # user_b is counterparty


def test_get_user_attestations_empty_for_unrelated_user(db):
    """get_user_attestations returns empty list for user with no attestations."""
    user_a = _user(db)
    svc = MeetupAttestationService(db)
    results = svc.get_user_attestations(user_a.id)
    assert results == []


# ---------------------------------------------------------------------------
# _on_confirmed — escrow released (line 116)
# ---------------------------------------------------------------------------

def test_on_confirmed_with_escrow_updates_status(db):
    """When attestation has escrow_id, _on_confirmed marks the escrow CONFIRMED (line 116)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)
    escrow = _escrow(db, user_a, user_b)

    svc = MeetupAttestationService(db)
    _make_confirmed_attestation(db, svc, user_a, user_b, match, escrow_id=escrow.id)

    db.refresh(escrow)
    assert escrow.status == EscrowStatus.CONFIRMED
    assert escrow.resolved_at is not None


# ---------------------------------------------------------------------------
# _on_confirmed — reputation updated for both parties (lines 121-122)
# ---------------------------------------------------------------------------

def test_on_confirmed_updates_reputation_for_both_parties(db):
    """_on_confirmed calls record_meetup_completed for both initiator and counterparty (lines 121-122)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    _make_confirmed_attestation(db, svc, user_a, user_b, match)

    score_a = db.query(ReputationScore).filter(ReputationScore.user_id == user_a.id).first()
    score_b = db.query(ReputationScore).filter(ReputationScore.user_id == user_b.id).first()

    # Both scores must exist and have improved above the 50.0 default
    assert score_a is not None, "Initiator reputation record should be created"
    assert score_b is not None, "Counterparty reputation record should be created"
    assert score_a.meetup_completion_score > 50.0
    assert score_b.meetup_completion_score > 50.0


# ---------------------------------------------------------------------------
# _on_confirmed — HCS anchoring (lines 126-132)
# ---------------------------------------------------------------------------

def test_on_confirmed_sets_hcs_message_id_when_anchor_returns_value(db):
    """When HCSAnchoringService.anchor_attestation returns a msg_id, it is stored on the attestation (line 116)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    fake_msg_id = "0.0.12345@1712345678.123456789"

    with patch(
        "app.services.meetup_attestation_service.HCSAnchoringService.anchor_attestation",
        return_value=fake_msg_id,
    ):
        svc = MeetupAttestationService(db)
        att = _make_confirmed_attestation(db, svc, user_a, user_b, match)

    assert att.hcs_message_id == fake_msg_id


def test_on_confirmed_does_not_set_hcs_message_id_when_anchor_returns_none(db):
    """When HCSAnchoringService.anchor_attestation returns None, hcs_message_id stays None (lines 126-132)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    with patch(
        "app.services.meetup_attestation_service.HCSAnchoringService.anchor_attestation",
        return_value=None,
    ):
        svc = MeetupAttestationService(db)
        att = _make_confirmed_attestation(db, svc, user_a, user_b, match)

    assert att.hcs_message_id is None


# ---------------------------------------------------------------------------
# _haversine — direct unit tests (lines 126-132)
# ---------------------------------------------------------------------------

def test_haversine_returns_999_when_any_coord_is_none(db):
    """_haversine early-exits with 999 when any coordinate is None (lines 126-127)."""
    svc = MeetupAttestationService(db)

    assert svc._haversine(None, -122.4194, 37.7749, -122.4194) == 999
    assert svc._haversine(37.7749, None, 37.7749, -122.4194) == 999
    assert svc._haversine(37.7749, -122.4194, None, -122.4194) == 999
    assert svc._haversine(37.7749, -122.4194, 37.7749, None) == 999
    assert svc._haversine(None, None, None, None) == 999


def test_haversine_same_point_returns_zero(db):
    """_haversine between identical coordinates must return 0 (full math path, lines 128-132)."""
    svc = MeetupAttestationService(db)
    result = svc._haversine(37.7749, -122.4194, 37.7749, -122.4194)
    assert result == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance(db):
    """_haversine between two known points returns approximately correct km distance."""
    svc = MeetupAttestationService(db)
    # SF City Hall → roughly 1 km north
    result = svc._haversine(37.7749, -122.4194, 37.7839, -122.4194)
    # Expect roughly 1 km (0.9-1.1)
    assert 0.9 < result < 1.1


def test_haversine_200m_apart(db):
    """Two points ~200 m apart should yield >0.1 km — used in GPS rejection logic."""
    svc = MeetupAttestationService(db)
    # ~200 m apart in latitude
    result = svc._haversine(37.7749, -122.4194, 37.7767, -122.4194)
    assert result > 0.1  # exceeds 100 m threshold


def test_haversine_50m_apart(db):
    """Two points ~50 m apart should yield <0.1 km — used in GPS acceptance logic."""
    svc = MeetupAttestationService(db)
    # ~50 m apart in latitude
    result = svc._haversine(37.7749, -122.4194, 37.77535, -122.4194)
    assert result < 0.1  # within 100 m threshold


# ---------------------------------------------------------------------------
# _get_or_404 — missing attestation (lines 121-122)
# ---------------------------------------------------------------------------

def test_confirm_nonexistent_attestation_raises_404(db):
    """confirm() on a non-existent attestation_id raises HTTPException 404 (lines 121-122)."""
    from fastapi import HTTPException

    user_a = _user(db)
    svc = MeetupAttestationService(db)

    with pytest.raises(HTTPException) as exc_info:
        svc.confirm(user_a, uuid.uuid4(), AttestationConfirm())

    assert exc_info.value.status_code == 404


def test_confirm_wrong_token_raises_attestation_error(db):
    """Token mismatch in confirm() raises AttestationError (line 50)."""
    user_a = _user(db)
    persona_a = _persona(db, user_a)
    user_b = _user(db)
    persona_b = _persona(db, user_b)
    match = _match(db, persona_a, persona_b)

    svc = MeetupAttestationService(db)
    att = svc.initiate(user_a, AttestationInitiate(
        match_id=match.id,
        method=AttestationMethod.QR_CODE,
    ))

    with pytest.raises(AttestationError, match="token"):
        svc.confirm(user_b, att.id, AttestationConfirm(token="TOTALLY_WRONG_TOKEN"))
