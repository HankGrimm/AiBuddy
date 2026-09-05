"""Tests for monadmate-reputation: ReputationEngine, decay, HCSAnchor."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from monadmate_reputation import ReputationDimensions, ReputationEngine, EventType, apply_decay, bulk_decay, HCSAnchor


# ---------------------------------------------------------------------------
# ReputationDimensions
# ---------------------------------------------------------------------------

def test_default_composite():
    score = ReputationDimensions()
    # All 50.0: 50*0.30 + 50*0.30 + 50*0.15 + 50*0.15 + 50*0.10 = 50.0
    assert score.composite == pytest.approx(50.0)


def test_composite_weighted():
    score = ReputationDimensions(reliability=100, safety=100, response_rate=0, meetup_completion=0, consent_score=0)
    # 100*0.30 + 100*0.30 = 60.0
    assert score.composite == pytest.approx(60.0)


def test_clamp_enforces_bounds():
    score = ReputationDimensions(reliability=150, safety=-10)
    score.clamp()
    assert score.reliability == 100.0
    assert score.safety == 0.0


# ---------------------------------------------------------------------------
# ReputationEngine — apply_event
# ---------------------------------------------------------------------------

def test_meetup_completed_increases_reliability():
    engine = ReputationEngine()
    score = ReputationDimensions()
    updated = engine.apply_event(score, EventType.MEETUP_COMPLETED)
    assert updated.reliability == pytest.approx(55.0)
    assert updated.meetup_completion == pytest.approx(55.0)
    assert updated.response_rate == pytest.approx(52.0)


def test_no_show_decreases_reliability():
    engine = ReputationEngine()
    score = ReputationDimensions()
    updated = engine.apply_event(score, EventType.NO_SHOW)
    assert updated.reliability == pytest.approx(35.0)
    assert updated.meetup_completion == pytest.approx(40.0)


def test_harassment_report_decreases_safety():
    engine = ReputationEngine()
    score = ReputationDimensions()
    updated = engine.apply_event(score, EventType.HARASSMENT_REPORT)
    assert updated.safety == pytest.approx(30.0)
    assert updated.consent_score == pytest.approx(40.0)


def test_stake_slashed_decreases_reliability_and_safety():
    engine = ReputationEngine()
    score = ReputationDimensions()
    updated = engine.apply_event(score, EventType.STAKE_SLASHED)
    assert updated.reliability == pytest.approx(30.0)
    assert updated.safety == pytest.approx(40.0)


def test_score_clamped_at_zero():
    engine = ReputationEngine()
    score = ReputationDimensions(safety=5.0)
    updated = engine.apply_event(score, EventType.HARASSMENT_REPORT)
    assert updated.safety == 0.0  # clamped, not negative


def test_score_clamped_at_100():
    engine = ReputationEngine()
    score = ReputationDimensions(reliability=98.0)
    updated = engine.apply_event(score, EventType.MEETUP_COMPLETED)
    assert updated.reliability == 100.0  # clamped, not 103


def test_from_history_builds_from_events():
    engine = ReputationEngine()
    events = [EventType.MEETUP_COMPLETED, EventType.MEETUP_COMPLETED, EventType.NO_SHOW]
    score = engine.from_history(events)
    # Started 50, +5+5-15 = 45 for reliability
    assert score.reliability == pytest.approx(45.0)


def test_unknown_event_is_noop():
    engine = ReputationEngine()
    score = ReputationDimensions()
    # If EventType has no delta, score unchanged
    updated = engine.apply_event(score, EventType.REPORT_DISMISSED)
    assert updated.safety == pytest.approx(55.0)  # +5 for dismissed report


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------

def test_apply_decay_no_effect_under_one_week():
    score = ReputationDimensions()
    now = datetime.utcnow()
    last_active = now - timedelta(days=5)
    updated = apply_decay(score, last_active, now)
    assert updated.reliability == pytest.approx(50.0)


def test_apply_decay_after_two_weeks():
    score = ReputationDimensions()
    now = datetime.utcnow()
    last_active = now - timedelta(weeks=2)
    updated = apply_decay(score, last_active, now)
    # 2 weeks * 1pt = 2pt decay
    assert updated.reliability == pytest.approx(48.0)
    assert updated.response_rate == pytest.approx(48.0)
    assert updated.meetup_completion == pytest.approx(48.0)
    # safety and consent NOT decayed
    assert updated.safety == pytest.approx(50.0)
    assert updated.consent_score == pytest.approx(50.0)


def test_apply_decay_floor_at_10():
    score = ReputationDimensions(reliability=10.5)
    now = datetime.utcnow()
    last_active = now - timedelta(weeks=100)
    updated = apply_decay(score, last_active, now)
    assert updated.reliability == pytest.approx(10.0)


def test_bulk_decay_calls_on_update():
    now = datetime.utcnow()
    updates = []
    users = [
        ("u1", ReputationDimensions(), now - timedelta(weeks=2)),
        ("u2", ReputationDimensions(), now - timedelta(days=3)),  # recent — skip
    ]
    count = bulk_decay(users, on_update=lambda uid, s: updates.append(uid), now=now)
    assert count == 1
    assert updates == ["u1"]


# ---------------------------------------------------------------------------
# HCSAnchor
# ---------------------------------------------------------------------------

def test_hcs_anchor_noop_when_unconfigured():
    anchor = HCSAnchor(topic_id=None, account_id=None, private_key=None)
    result = anchor.anchor_reputation_event(
        user_id="u1", event_type="meetup_completed",
        dimension_deltas={}, composite_before=50.0, composite_after=55.0
    )
    assert result is None


def test_hcs_anchor_is_configured():
    anchor = HCSAnchor(topic_id="0.0.123", account_id="0.0.456", private_key="abc")
    assert anchor.is_configured is True


def test_hcs_anchor_not_configured_without_topic():
    anchor = HCSAnchor(topic_id=None, account_id="0.0.456", private_key="abc")
    assert anchor.is_configured is False


@patch("monadmate_reputation.hcs.httpx.post")
def test_hcs_anchor_publishes_on_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"sequence_number": 42}
    mock_post.return_value = mock_response

    anchor = HCSAnchor(topic_id="0.0.123", account_id="0.0.456", private_key="key")
    result = anchor.anchor_reputation_event(
        user_id="u1", event_type="no_show",
        dimension_deltas={"reliability": -15}, composite_before=50.0, composite_after=35.0
    )
    assert result == "42"
    mock_post.assert_called_once()


@patch("monadmate_reputation.hcs.httpx.post")
def test_hcs_anchor_returns_none_on_http_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    anchor = HCSAnchor(topic_id="0.0.123", account_id="0.0.456", private_key="key")
    result = anchor.anchor_stake_decision("s1", "u1", "slash", 1.0)
    assert result is None
