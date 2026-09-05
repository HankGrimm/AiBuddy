"""
Extended reputation decay + social reputation service coverage.
"""
import uuid
from datetime import datetime, timedelta

import pytest

from app.models.attestation import MeetupAttestation, AttestationStatus, AttestationMethod
from app.models.match import Match, MatchStatus
from app.models.persona import Persona, IntentMode
from app.models.reputation import ReputationScore, ReputationEventType
from app.models.room import Room, RoomType, RoomPrivacyLevel
from app.models.user import User, VerificationLevel, PrivacyMode
from app.services.reputation_decay_service import ReputationDecayService
from app.services.social_reputation_service import SocialReputationService
from app.schemas.reputation import FeedbackCreate
from app.core.errors import PersonaNotFoundError


def _user(db) -> User:
    u = User(
        id=uuid.uuid4(),
        wallet_address=f"w_{uuid.uuid4().hex[:8]}",
        verification_level=VerificationLevel.WALLET,
        privacy_mode=PrivacyMode.SEMI_PRIVATE,
    )
    db.add(u)
    db.commit()
    return u


def _score(db, user: User, **kwargs) -> ReputationScore:
    defaults = dict(
        reliability_score=50.0,
        safety_score=50.0,
        response_score=50.0,
        meetup_completion_score=50.0,
        consent_confirmation_score=50.0,
    )
    defaults.update(kwargs)
    s = ReputationScore(id=uuid.uuid4(), user_id=user.id, **defaults)
    db.add(s)
    db.commit()
    return s


# ── apply_decay ───────────────────────────────────────────────────────────────

def test_no_decay_within_one_week(db):
    user = _user(db)
    s = _score(db, user, meetup_completion_score=60.0)
    s.last_decay_at = datetime.utcnow() - timedelta(days=3)
    db.commit()

    svc = ReputationDecayService(db)
    result = svc.apply_decay(user.id)
    assert result.meetup_completion_score == pytest.approx(60.0)


def test_decay_clamps_at_zero(db):
    user = _user(db)
    s = _score(db, user, safety_score=1.0)
    s.last_decay_at = datetime.utcnow() - timedelta(days=100)
    db.commit()

    svc = ReputationDecayService(db)
    result = svc.apply_decay(user.id)
    assert result.safety_score == pytest.approx(0.0)


def test_decay_returns_none_for_missing_score(db):
    user = _user(db)
    svc = ReputationDecayService(db)
    result = svc.apply_decay(user.id)
    assert result is None


def test_decay_uses_updated_at_when_last_decay_at_is_none(db):
    user = _user(db)
    s = _score(db, user, reliability_score=80.0)
    s.updated_at = datetime.utcnow() - timedelta(days=14)
    s.last_decay_at = None
    db.commit()

    svc = ReputationDecayService(db)
    result = svc.apply_decay(user.id)
    # 2 weeks × 1 pt decay → 78.0
    assert result.reliability_score == pytest.approx(78.0, abs=0.01)


# ── apply_bulk_decay ──────────────────────────────────────────────────────────

def test_bulk_decay_processes_stale_scores(db):
    users = [_user(db) for _ in range(3)]
    for u in users:
        s = _score(db, u)
        s.last_decay_at = datetime.utcnow() - timedelta(days=14)
        db.commit()

    # One fresh user — should not be processed
    fresh_user = _user(db)
    s_fresh = _score(db, fresh_user)
    s_fresh.last_decay_at = datetime.utcnow()
    db.commit()

    svc = ReputationDecayService(db)
    count = svc.apply_bulk_decay(days_inactive_threshold=7)
    assert count == 3


def test_bulk_decay_zero_when_all_fresh(db):
    user = _user(db)
    s = _score(db, user)
    s.last_decay_at = datetime.utcnow()
    db.commit()

    svc = ReputationDecayService(db)
    count = svc.apply_bulk_decay(days_inactive_threshold=7)
    assert count == 0


# ── SocialReputationService ───────────────────────────────────────────────────

def test_get_or_create_creates_new_score(db):
    user = _user(db)
    svc = SocialReputationService(db)

    score = svc.get_or_create(user.id)
    assert score.user_id == user.id
    assert score.id is not None


def test_get_or_create_is_idempotent(db):
    user = _user(db)
    svc = SocialReputationService(db)

    s1 = svc.get_or_create(user.id)
    s2 = svc.get_or_create(user.id)
    assert s1.id == s2.id


def test_record_feedback_meetup_completed_boosts_score(db):
    user = _user(db)
    svc = SocialReputationService(db)
    score = svc.get_or_create(user.id)
    original = score.meetup_completion_score

    ref_id = uuid.uuid4()
    svc.record_feedback(
        User(id=uuid.uuid4(), wallet_address="w_x", is_active=True),
        FeedbackCreate(
            target_user_id=user.id,
            reference_id=ref_id,
            event_type=ReputationEventType.MEETUP_COMPLETED,
        )
    )

    db.refresh(score)
    assert score.meetup_completion_score > original


def test_record_feedback_report_reduces_safety_score(db):
    user = _user(db)
    svc = SocialReputationService(db)
    score = svc.get_or_create(user.id)
    original_safety = score.safety_score

    reporter = User(id=uuid.uuid4(), wallet_address="w_r", is_active=True)
    svc.record_feedback(
        reporter,
        FeedbackCreate(
            target_user_id=user.id,
            reference_id=uuid.uuid4(),
            event_type=ReputationEventType.REPORT_RECEIVED,
        )
    )

    db.refresh(score)
    assert score.safety_score < original_safety


def test_record_meetup_completed_increments_total(db):
    user = _user(db)
    svc = SocialReputationService(db)
    svc.record_meetup_completed(user.id)
    svc.record_meetup_completed(user.id)

    score = svc.get_or_create(user.id)
    assert score.total_meetups == 2


def test_apply_delta_clamps_at_100(db):
    user = _user(db)
    svc = SocialReputationService(db)
    score = svc.get_or_create(user.id)
    score.reliability_score = 99.0
    svc._apply_delta(score, "reliability_score", 10.0)
    assert score.reliability_score == pytest.approx(100.0)


def test_apply_delta_clamps_at_zero(db):
    user = _user(db)
    svc = SocialReputationService(db)
    score = svc.get_or_create(user.id)
    score.safety_score = 2.0
    svc._apply_delta(score, "safety_score", -50.0)
    assert score.safety_score == pytest.approx(0.0)


# ── get_by_persona ─────────────────────────────────────────────────────────────

def _persona(db, user: User) -> Persona:
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="TestP",
        intent_mode=IntentMode.SOCIAL,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_get_by_persona_returns_score(db):
    user = _user(db)
    persona = _persona(db, user)
    svc = SocialReputationService(db)

    score = svc.get_by_persona(persona.id)

    assert score is not None
    assert score.user_id == user.id


def test_get_by_persona_creates_score_if_missing(db):
    """Persona exists but no ReputationScore yet — should auto-create."""
    user = _user(db)
    persona = _persona(db, user)
    svc = SocialReputationService(db)

    # Confirm no score exists yet
    existing = db.query(ReputationScore).filter(ReputationScore.user_id == user.id).first()
    assert existing is None

    score = svc.get_by_persona(persona.id)
    assert score.user_id == user.id


def test_get_by_persona_raises_404_for_unknown_persona(db):
    svc = SocialReputationService(db)
    with pytest.raises(PersonaNotFoundError):
        svc.get_by_persona(uuid.uuid4())


# ── process_attestation ────────────────────────────────────────────────────────

def _make_match(db, user_a: User, user_b: User) -> Match:
    room = Room(
        id=uuid.uuid4(), name="MatchRoom", type=RoomType.LOUNGE,
        privacy_level=RoomPrivacyLevel.PUBLIC, stake_required=0.0,
        intent_modes=[], is_active=True,
    )
    db.add(room)
    db.commit()

    persona_a = Persona(id=uuid.uuid4(), user_id=user_a.id, display_name="PA",
                        intent_mode=IntentMode.SOCIAL, is_active=True)
    persona_b = Persona(id=uuid.uuid4(), user_id=user_b.id, display_name="PB",
                        intent_mode=IntentMode.SOCIAL, is_active=True)
    db.add_all([persona_a, persona_b])
    db.commit()

    match = Match(
        id=uuid.uuid4(),
        requester_persona_id=persona_a.id,
        target_persona_id=persona_b.id,
        room_id=room.id,
        status=MatchStatus.ACCEPTED,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def _make_attestation(db, match: Match, initiator: User, counterparty: User,
                       status: AttestationStatus) -> MeetupAttestation:
    att = MeetupAttestation(
        id=uuid.uuid4(),
        match_id=match.id,
        initiator_user_id=initiator.id,
        counterparty_user_id=counterparty.id,
        method=AttestationMethod.GPS_CHECKIN,
        status=status,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def test_process_attestation_confirmed_boosts_both_users(db):
    user_a = _user(db)
    user_b = _user(db)
    match = _make_match(db, user_a, user_b)
    att = _make_attestation(db, match, user_a, user_b, AttestationStatus.CONFIRMED)

    svc = SocialReputationService(db)
    svc.process_attestation(att.id)

    score_a = svc.get_or_create(user_a.id)
    score_b = svc.get_or_create(user_b.id)

    # Both should have total_meetups incremented
    assert score_a.total_meetups >= 1
    assert score_b.total_meetups >= 1
    # meetup_completion_score boosted above default 50
    assert score_a.meetup_completion_score > 50.0
    assert score_b.meetup_completion_score > 50.0


def test_process_attestation_non_confirmed_does_nothing(db):
    user_a = _user(db)
    user_b = _user(db)
    match = _make_match(db, user_a, user_b)
    att = _make_attestation(db, match, user_a, user_b, AttestationStatus.FAILED)

    svc = SocialReputationService(db)
    svc.process_attestation(att.id)

    # Scores should not have been created (no-op)
    score_a = db.query(ReputationScore).filter(ReputationScore.user_id == user_a.id).first()
    assert score_a is None


def test_process_attestation_unknown_id_does_nothing(db):
    svc = SocialReputationService(db)
    # Should not raise — just silently no-op
    svc.process_attestation(uuid.uuid4())


def test_process_attestation_only_initiator_set(db):
    """If counterparty_user_id is None, only initiator gets the boost."""
    user_a = _user(db)
    user_b = _user(db)
    match = _make_match(db, user_a, user_b)
    att = MeetupAttestation(
        id=uuid.uuid4(),
        match_id=match.id,
        initiator_user_id=user_a.id,
        counterparty_user_id=None,
        method=AttestationMethod.GPS_CHECKIN,
        status=AttestationStatus.CONFIRMED,
    )
    db.add(att)
    db.commit()

    svc = SocialReputationService(db)
    svc.process_attestation(att.id)

    score_a = svc.get_or_create(user_a.id)
    assert score_a.total_meetups >= 1


# ── all DIMENSION_MAP event types ─────────────────────────────────────────────

@pytest.mark.parametrize("event_type,dimension,direction", [
    (ReputationEventType.MEETUP_COMPLETED,   "meetup_completion_score", +1),
    (ReputationEventType.MEETUP_NO_SHOW,     "meetup_completion_score", -1),
    (ReputationEventType.MESSAGE_RESPONDED,  "response_score",          +1),
    (ReputationEventType.MESSAGE_IGNORED,    "response_score",          -1),
    (ReputationEventType.REPORT_RECEIVED,    "safety_score",            -1),
    (ReputationEventType.STAKE_SLASHED,      "reliability_score",       -1),
    (ReputationEventType.CONSENT_CONFIRMED,  "consent_confirmation_score", +1),
    (ReputationEventType.POSITIVE_FEEDBACK,  "reliability_score",       +1),
    (ReputationEventType.NEGATIVE_FEEDBACK,  "reliability_score",       -1),
])
def test_dimension_map_all_event_types(db, event_type, dimension, direction):
    user = _user(db)
    svc = SocialReputationService(db)
    score = svc.get_or_create(user.id)
    before = getattr(score, dimension)

    reporter = User(id=uuid.uuid4(), wallet_address=f"rep_{uuid.uuid4().hex[:6]}", is_active=True)
    svc.record_feedback(
        reporter,
        FeedbackCreate(
            target_user_id=user.id,
            reference_id=uuid.uuid4(),
            event_type=event_type,
        )
    )

    db.refresh(score)
    after = getattr(score, dimension)
    if direction > 0:
        assert after >= before  # may hit 100 cap
    else:
        assert after <= before  # may hit 0 floor
