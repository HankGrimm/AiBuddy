"""
monadmate-reputation — Portable on-chain reputation for Web3 social apps

5-dimension reputation scoring with time-based decay and Hedera HCS anchoring.
Zero Monad Mate dependencies — works with any SQLAlchemy app.

Install: pip install monadmate-reputation

Features:
  - 5-dimension reputation: reliability, safety, response_rate, meetup_completion, consent
  - Event-driven updates: meetup_completed (+5), no_show (-15), harassment_report (-10), slash (-20)
  - Time decay: -1pt/week per dimension for inactive users
  - Hedera HCS anchoring: immutable audit log for every safety decision
  - Graceful no-op when Hedera not configured
"""

from .scoring import ReputationDimensions, ReputationEngine, EventType
from .decay import apply_decay, bulk_decay
from .hcs import HCSAnchor

__version__ = "0.1.0"
__all__ = [
    "ReputationDimensions",
    "ReputationEngine",
    "EventType",
    "apply_decay",
    "bulk_decay",
    "HCSAnchor",
]
