# monadmate-stake-sdk

> Stake-gated access control for Web3 social apps. Require a USDC stake before any action — DMs, room entry, meetup requests. Extracted from Monad Mate Trust API.

[![PyPI](https://img.shields.io/pypi/v/monadmate-stake-sdk)](https://pypi.org/project/monadmate-stake-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

No ORM or framework dependencies — bring your own storage and payment layer.

## Install

```bash
pip install monadmate-stake-sdk
```

## Usage

```python
from monadmate_stake_sdk import StakeGate, StakeType, SlashingPolicy, SlashReason

# Create a gate with custom minimums (falls back to defaults)
gate = StakeGate(
    min_amounts={
        StakeType.DM: 0.50,
        StakeType.MEETUP_REQUEST: 1.00,
    }
)

# Validate before accepting payment
ok, error = gate.validate(StakeType.DM, amount_usdc=0.50, no_show_count=0)
# ok=True, error=""

# Repeat offender — 2 no-shows raises DM stake to 1.50 USDC (3× base)
ok, error = gate.validate(StakeType.DM, amount_usdc=0.50, no_show_count=2)
# ok=False, error="Minimum stake for dm is 1.50 USDC (you sent 0.50)"

# Create and activate a stake record
record = gate.create_stake(
    user_id="0xABC123",
    stake_type=StakeType.DM,
    amount_usdc=0.50,
)
# record.status == StakeStatus.ACTIVE

# Refund on success
gate.refund_stake(record)
# record.status == StakeStatus.REFUNDED

# Slash on violation
gate.slash_stake(record, reason="no_show")
# record.status == StakeStatus.SLASHED
```

## Stake Types

| Type | Default Minimum | Use Case |
|------|----------------|----------|
| `DM` | 0.50 USDC | Direct message unlock |
| `ROOM_ENTRY` | 0.10 USDC | Enter a social room |
| `MEETUP_REQUEST` | 1.00 USDC | Request an IRL meetup |
| `PHOTO_UNLOCK` | 0.25 USDC | View private photos |
| `MEETUP_CONFIRM` | 1.00 USDC | Confirm attendance |

## No-Show Multiplier

Each no-show increases the required stake by 0.5×, capped at 3×:

| No-Shows | Multiplier | DM Stake |
|----------|-----------|----------|
| 0 | 1.0× | 0.50 USDC |
| 1 | 1.5× | 0.75 USDC |
| 2 | 2.0× | 1.00 USDC |
| 4+ | 3.0× | 1.50 USDC (max) |

```python
required = gate.required_amount(StakeType.DM, no_show_count=2)
# 1.00 USDC
```

## Slashing Policy

```python
from monadmate_stake_sdk import SlashingPolicy, SlashReason

policy = SlashingPolicy()

# Evaluate — always slash harassment regardless of history
decision = policy.evaluate(SlashReason.HARASSMENT, stake_amount=1.00)
# decision.should_slash = True, decision.slash_pct = 1.0

# No-show only slashes after 1 incident
decision = policy.evaluate(SlashReason.NO_SHOW, no_show_count=0)
# decision.should_slash = False

decision = policy.evaluate(SlashReason.NO_SHOW, no_show_count=1, stake_amount=0.50)
# decision.should_slash = True, decision.slash_pct = 1.0

# Calculate slash amount
amount = policy.slash_amount(stake_amount=1.00, reason=SlashReason.SPAM)
# 0.50 USDC (50% for spam)
```

## Slash Reasons

| Reason | Slash % | Requires History? |
|--------|---------|-------------------|
| `NO_SHOW` | 100% | 1+ no-show |
| `HARASSMENT` | 100% | Never (always slash) |
| `FAKE_PROFILE` | 100% | Never (always slash) |
| `CONSENT_VIOLATION` | 100% | Never (always slash) |
| `SPAM` | 50% | 2+ reports |
| `PAYMENT_FRAUD` | 100% | Never (always slash) |

## Hooks / Callbacks

```python
def on_stake(record):
    db.save(record)
    circle.hold_funds(record.id, record.amount_usdc)

def on_refund(record):
    circle.release_funds(record.id)

def on_slash(record, reason):
    circle.capture_funds(record.id)
    notify_safety_team(record.user_id, reason)

gate = StakeGate(on_stake=on_stake, on_refund=on_refund, on_slash=on_slash)
```

## StakeRecord Fields

```python
@dataclass
class StakeRecord:
    id: str                        # UUID
    user_id: str
    stake_type: StakeType
    amount_usdc: float
    status: StakeStatus            # PENDING → ACTIVE → REFUNDED/SLASHED
    room_id: Optional[str]
    reference_id: Optional[str]    # match_id, dm_id, etc.
    monad_tx_hash: Optional[str]   # EventLog tx hash
    circle_transfer_id: Optional[str]
    created_at: datetime
    updated_at: datetime
```

## License

MIT — extracted from [Monad Mate Trust API](https://github.com/AINative-Studio/monad-mate-trust-api). Built for EasyA × Consensus Miami 2026.
