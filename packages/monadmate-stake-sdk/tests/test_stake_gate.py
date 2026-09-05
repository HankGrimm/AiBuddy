"""Tests for monadmate-stake-sdk: StakeGate and SlashingPolicy."""
import pytest
from monadmate_stake_sdk import StakeGate, StakeType, StakeStatus, StakeRecord, SlashingPolicy, SlashReason


# ---------------------------------------------------------------------------
# StakeGate — required_amount
# ---------------------------------------------------------------------------

def test_required_amount_defaults():
    gate = StakeGate()
    assert gate.required_amount(StakeType.DM) == 0.50
    assert gate.required_amount(StakeType.ROOM_ENTRY) == 0.10
    assert gate.required_amount(StakeType.MEETUP_REQUEST) == 1.00


def test_required_amount_no_show_multiplier():
    gate = StakeGate()
    # 1 no-show: base * 1.5
    assert gate.required_amount(StakeType.DM, no_show_count=1) == pytest.approx(0.75)
    # 2 no-shows: base * 2.0
    assert gate.required_amount(StakeType.DM, no_show_count=2) == pytest.approx(1.00)


def test_required_amount_capped_at_max_multiplier():
    gate = StakeGate()
    # 10 no-shows: capped at 3x
    assert gate.required_amount(StakeType.DM, no_show_count=10) == pytest.approx(1.50)


def test_required_amount_custom_overrides():
    gate = StakeGate(min_amounts={StakeType.DM: 2.00})
    assert gate.required_amount(StakeType.DM) == 2.00
    assert gate.required_amount(StakeType.ROOM_ENTRY) == 0.10  # default unchanged


# ---------------------------------------------------------------------------
# StakeGate — validate
# ---------------------------------------------------------------------------

def test_validate_passes():
    gate = StakeGate()
    ok, msg = gate.validate(StakeType.DM, 0.50)
    assert ok is True
    assert msg == ""


def test_validate_fails_below_minimum():
    gate = StakeGate()
    ok, msg = gate.validate(StakeType.DM, 0.10)
    assert ok is False
    assert "0.50" in msg


def test_validate_exact_minimum_passes():
    gate = StakeGate()
    ok, _ = gate.validate(StakeType.MEETUP_REQUEST, 1.00)
    assert ok is True


# ---------------------------------------------------------------------------
# StakeGate — create_stake
# ---------------------------------------------------------------------------

def test_create_stake_returns_active_record():
    gate = StakeGate()
    record = gate.create_stake(user_id="user1", stake_type=StakeType.DM, amount_mon=0.50)
    assert record.status == StakeStatus.ACTIVE
    assert record.user_id == "user1"
    assert record.stake_type == StakeType.DM
    assert record.amount_mon == 0.50
    assert record.id is not None


def test_create_stake_raises_on_insufficient_amount():
    gate = StakeGate()
    with pytest.raises(ValueError, match="Minimum stake"):
        gate.create_stake(user_id="user1", stake_type=StakeType.DM, amount_mon=0.01)


def test_create_stake_triggers_on_stake_callback():
    called = []
    gate = StakeGate(on_stake=lambda r: called.append(r))
    gate.create_stake(user_id="u1", stake_type=StakeType.DM, amount_mon=1.0)
    assert len(called) == 1
    assert called[0].user_id == "u1"


# ---------------------------------------------------------------------------
# StakeGate — refund / slash
# ---------------------------------------------------------------------------

def test_refund_stake_sets_status():
    gate = StakeGate()
    record = gate.create_stake("u1", StakeType.DM, 1.0)
    gate.refund_stake(record)
    assert record.status == StakeStatus.REFUNDED


def test_slash_stake_sets_status():
    gate = StakeGate()
    record = gate.create_stake("u1", StakeType.DM, 1.0)
    gate.slash_stake(record, "no_show")
    assert record.status == StakeStatus.SLASHED


def test_slash_triggers_callback():
    reasons = []
    gate = StakeGate(on_slash=lambda r, reason: reasons.append(reason))
    record = gate.create_stake("u1", StakeType.DM, 1.0)
    gate.slash_stake(record, "harassment")
    assert reasons == ["harassment"]


# ---------------------------------------------------------------------------
# SlashingPolicy
# ---------------------------------------------------------------------------

def test_always_slash_reasons():
    policy = SlashingPolicy()
    for reason in [SlashReason.HARASSMENT, SlashReason.CONSENT_VIOLATION,
                   SlashReason.FAKE_PROFILE, SlashReason.PAYMENT_FRAUD]:
        decision = policy.evaluate(reason, no_show_count=0)
        assert decision.should_slash is True
        assert decision.slash_pct == 1.0


def test_no_show_first_offense_slashes():
    policy = SlashingPolicy()
    decision = policy.evaluate(SlashReason.NO_SHOW, no_show_count=1)
    assert decision.should_slash is True
    assert decision.slash_pct == 1.0


def test_spam_requires_two_incidents():
    policy = SlashingPolicy()
    d1 = policy.evaluate(SlashReason.SPAM, no_show_count=1)
    assert d1.should_slash is False
    d2 = policy.evaluate(SlashReason.SPAM, no_show_count=2)
    assert d2.should_slash is True
    assert d2.slash_pct == 0.5


def test_slash_amount_calculation():
    policy = SlashingPolicy()
    assert policy.slash_amount(10.0, SlashReason.NO_SHOW) == pytest.approx(10.0)
    assert policy.slash_amount(10.0, SlashReason.SPAM) == pytest.approx(5.0)


def test_slash_decision_has_explanation():
    policy = SlashingPolicy()
    decision = policy.evaluate(SlashReason.NO_SHOW, no_show_count=1)
    assert len(decision.explanation) > 0
