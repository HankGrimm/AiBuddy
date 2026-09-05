# monadmate-reputation

> Portable 5-dimension reputation scoring with time-based decay and Hedera HCS anchoring. Built for Web3 social apps.

[![PyPI](https://img.shields.io/pypi/v/monadmate-reputation)](https://pypi.org/project/monadmate-reputation/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

Extracted from [Monad Mate Trust API](https://github.com/HankGrimm/monad-mate-trust-api). No ORM or framework dependencies — bring your own storage.

## Install

```bash
pip install monadmate-reputation
```

## Usage

```python
from monadmate_reputation import ReputationDimensions, ReputationEngine, EventType, HCSAnchor, apply_decay

# Scoring
engine = ReputationEngine()
score = ReputationDimensions()  # starts at 50/100 per dimension

score = engine.apply_event(score, EventType.MEETUP_COMPLETED)
# reliability +5, meetup_completion +5, response_rate +2

score = engine.apply_event(score, EventType.NO_SHOW)
# reliability -15, meetup_completion -10

print(score.composite)  # 0-100 weighted composite

# Time decay
from datetime import datetime, timedelta
last_active = datetime.utcnow() - timedelta(days=14)
score = apply_decay(score, last_active)
# -2pt on reliability/response_rate/meetup_completion (2 weeks)

# HCS anchoring (optional — no-ops if not configured)
hcs = HCSAnchor(topic_id="0.0.1234567")
hcs.anchor_reputation_event(
    user_id="user-123",
    event_type="meetup_completed",
    dimension_deltas={"reliability": 5, "meetup_completion": 5},
    composite_before=60.0,
    composite_after=63.2,
)
```

## Event Types

| Event | reliability | safety | response_rate | meetup_completion | consent |
|-------|------------|--------|---------------|-------------------|---------|
| `MEETUP_COMPLETED` | +5 | — | +2 | +5 | — |
| `NO_SHOW` | -15 | — | — | -10 | — |
| `HARASSMENT_REPORT` | — | -20 | — | — | -10 |
| `STAKE_SLASHED` | -20 | -10 | — | — | — |
| `STAKE_REFUNDED` | +3 | — | — | +3 | — |
| `CONSENT_CONFIRMED` | — | — | — | — | +5 |

## Composite Score

```
composite = reliability × 0.30 + safety × 0.30 + response_rate × 0.15
          + meetup_completion × 0.15 + consent × 0.10
```

## Decay

Decay applies -1pt/week to `reliability`, `response_rate`, `meetup_completion` for inactive users. Floor at 10.

```python
from monadmate_reputation import bulk_decay

def save_score(user_id, score):
    db.update(user_id, score)

bulk_decay(
    users=[(u.id, u.score, u.last_active) for u in db.query(...)],
    on_update=save_score,
    days_inactive_threshold=7,
)
```

## HCS Anchoring

Set environment variables or pass directly:

```env
HEDERA_ACCOUNT_ID=0.0.9876
HEDERA_PRIVATE_KEY=your-ed25519-hex
HEDERA_TOPIC_ID=0.0.1234567
HEDERA_NETWORK=testnet  # or mainnet
```

HCSAnchor no-ops gracefully when not configured.

## License

MIT — extracted from [Monad Mate Trust API](https://github.com/HankGrimm/monad-mate-trust-api). Built for EasyA × Consensus Miami 2026.
