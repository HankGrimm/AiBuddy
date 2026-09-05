"""
Sprint 4 — Reputation Engine tests
Covers: composite score calculation, decay, and no-show penalties.
"""
import uuid
import pytest
from datetime import datetime, timedelta

from app.models.reputation import ReputationScore, ReputationEvent, ReputationEventType
from app.models.user import User, VerificationLevel, PrivacyMode
from app.services.reputation_event_processor import ReputationEventProcessor
from app.services.reputation_decay_service import ReputationDecayService
from app.services.social_reputation_service import SocialReputationService


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


def make_score(db, user: User, **kwargs) -> ReputationScore:
    defaults = dict(
        reliability_score=60.0,
        safety_score=70.0,
        response_score=55.0,
        meetup_completion_score=65.0,
        consent_confirmation_score=50.0,
    )
    defaults.update(kwargs)
    score = ReputationScore(id=uuid.uuid4(), user_id=user.id, **defaults)
    db.add(score)
    db.commit()
    return score


# ------------------------------------------------------------------ composite score
def test_reputation_composite_score_calculation(db):
    user = make_user(db)
    score = make_score(db, user)
    svc = SocialReputationService(db)
    # trigger a recalculation
    svc._recalculate_composite(score)
    db.commit()

    expected = (
        score.reliability_score * 0.25
        + score.safety_score * 0.30
        + score.response_score * 0.15
        + score.meetup_completion_score * 0.20
        + score.consent_confirmation_score * 0.10
    )
    assert abs(score.composite_score - expected) < 0.01


# ------------------------------------------------------------------ decay
def test_reputation_decay_applied(db):
    user = make_user(db)
    score = make_score(db, user, meetup_completion_score=60.0)
    # Force last_decay_at to 14 days ago → 2 full weeks → 2 pts decay
    score.last_decay_at = datetime.utcnow() - timedelta(days=14, seconds=1)
    db.commit()

    decay_svc = ReputationDecayService(db)
    updated = decay_svc.apply_decay(user.id)

    # 2 weeks × 1 pt = 2 pts decay on meetup_completion_score (was 60.0 → 58.0)
    assert updated.meetup_completion_score == pytest.approx(58.0, abs=0.01)
    assert updated.last_decay_at is not None
    # composite should also have been recalculated
    assert updated.composite_score > 0


# ------------------------------------------------------------------ no-show penalty
def test_no_show_reduces_meetup_score(db):
    user = make_user(db)
    match_id = uuid.uuid4()

    processor = ReputationEventProcessor(db)
    score = processor.process_no_show(user.id, match_id)

    # default meetup_completion_score starts at 50, no-show -15 → 35
    assert score.meetup_completion_score == pytest.approx(35.0, abs=0.01)

    events = processor.get_event_history(user.id)
    assert len(events) == 1
    assert events[0].event_type == ReputationEventType.MEETUP_NO_SHOW
    assert events[0].delta == pytest.approx(-15.0, abs=0.01)
