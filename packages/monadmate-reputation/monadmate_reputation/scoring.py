"""
Reputation scoring engine — domain-agnostic, no ORM dependency.

Works with any storage backend via the ReputationStore protocol.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


class EventType(str, enum.Enum):
    MEETUP_COMPLETED = "meetup_completed"
    NO_SHOW = "no_show"
    HARASSMENT_REPORT = "harassment_report"
    FAKE_PROFILE_REPORT = "fake_profile_report"
    STAKE_SLASHED = "stake_slashed"
    STAKE_REFUNDED = "stake_refunded"
    CONSENT_CONFIRMED = "consent_confirmed"
    RESPONSE_POSITIVE = "response_positive"
    RESPONSE_IGNORED = "response_ignored"
    REPORT_DISMISSED = "report_dismissed"


@dataclass
class ReputationDimensions:
    """5-dimension reputation score. All values in [0, 100]."""
    reliability: float = 50.0         # Shows up, doesn't ghost
    safety: float = 50.0              # No harassment/reports
    response_rate: float = 50.0       # Responds to messages
    meetup_completion: float = 50.0   # Completes confirmed meetups
    consent_score: float = 50.0       # Explicit consent confirmations

    @property
    def composite(self) -> float:
        """Weighted composite: reliability 30%, safety 30%, response 15%, meetup 15%, consent 10%."""
        return round(
            self.reliability * 0.30
            + self.safety * 0.30
            + self.response_rate * 0.15
            + self.meetup_completion * 0.15
            + self.consent_score * 0.10,
            2,
        )

    def clamp(self) -> "ReputationDimensions":
        """Clamp all values to [0, 100]."""
        self.reliability = max(0.0, min(100.0, self.reliability))
        self.safety = max(0.0, min(100.0, self.safety))
        self.response_rate = max(0.0, min(100.0, self.response_rate))
        self.meetup_completion = max(0.0, min(100.0, self.meetup_completion))
        self.consent_score = max(0.0, min(100.0, self.consent_score))
        return self


# Event → dimension delta map
_EVENT_DELTAS: dict[EventType, dict[str, float]] = {
    EventType.MEETUP_COMPLETED: {
        "reliability": +5.0,
        "meetup_completion": +5.0,
        "response_rate": +2.0,
    },
    EventType.NO_SHOW: {
        "reliability": -15.0,
        "meetup_completion": -10.0,
    },
    EventType.HARASSMENT_REPORT: {
        "safety": -20.0,
        "consent_score": -10.0,
    },
    EventType.FAKE_PROFILE_REPORT: {
        "safety": -15.0,
        "reliability": -5.0,
    },
    EventType.STAKE_SLASHED: {
        "reliability": -20.0,
        "safety": -10.0,
    },
    EventType.STAKE_REFUNDED: {
        "reliability": +3.0,
        "meetup_completion": +3.0,
    },
    EventType.CONSENT_CONFIRMED: {
        "consent_score": +5.0,
    },
    EventType.RESPONSE_POSITIVE: {
        "response_rate": +2.0,
    },
    EventType.RESPONSE_IGNORED: {
        "response_rate": -3.0,
    },
    EventType.REPORT_DISMISSED: {
        "safety": +5.0,  # false report vindicated
    },
}


class ReputationEngine:
    """
    Stateless reputation computation engine.

    Usage:
        engine = ReputationEngine()
        score = engine.apply_event(current_score, EventType.MEETUP_COMPLETED)
    """

    def apply_event(
        self, score: ReputationDimensions, event: EventType
    ) -> ReputationDimensions:
        """Apply an event's delta to a reputation score. Returns updated score."""
        deltas = _EVENT_DELTAS.get(event, {})
        for dimension, delta in deltas.items():
            current = getattr(score, dimension, 50.0)
            setattr(score, dimension, current + delta)
        return score.clamp()

    def from_history(self, events: list[EventType]) -> ReputationDimensions:
        """Build a fresh score from an ordered list of events."""
        score = ReputationDimensions()
        for event in events:
            score = self.apply_event(score, event)
        return score
