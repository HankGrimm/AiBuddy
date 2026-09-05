"""
Slashing policy — defines when and how stakes are slashed.

Framework-agnostic. Bring your own storage.

Usage:
    policy = SlashingPolicy()
    decision = policy.evaluate(reason=SlashReason.NO_SHOW, no_show_count=2)
    if decision.should_slash:
        gate.slash_stake(record, decision.reason)
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


class SlashReason(str, enum.Enum):
    NO_SHOW = "no_show"
    HARASSMENT = "harassment"
    FAKE_PROFILE = "fake_profile"
    CONSENT_VIOLATION = "consent_violation"
    SPAM = "spam"
    PAYMENT_FRAUD = "payment_fraud"


# Slash percentages per reason (0.0 – 1.0)
_DEFAULT_SLASH_PCT: dict[SlashReason, float] = {
    SlashReason.NO_SHOW: 1.0,           # Full slash — you didn't show up
    SlashReason.HARASSMENT: 1.0,        # Full slash — safety violation
    SlashReason.FAKE_PROFILE: 1.0,      # Full slash — fraud
    SlashReason.CONSENT_VIOLATION: 1.0, # Full slash — safety violation
    SlashReason.SPAM: 0.5,              # Half slash — nuisance
    SlashReason.PAYMENT_FRAUD: 1.0,     # Full slash — fraud
}

# Reasons that always slash regardless of prior record
_ALWAYS_SLASH: frozenset[SlashReason] = frozenset({
    SlashReason.HARASSMENT,
    SlashReason.FAKE_PROFILE,
    SlashReason.CONSENT_VIOLATION,
    SlashReason.PAYMENT_FRAUD,
})

# Reasons that require a minimum no-show count before slashing
_MIN_NO_SHOW_TO_SLASH: dict[SlashReason, int] = {
    SlashReason.NO_SHOW: 1,   # First no-show = slash
    SlashReason.SPAM: 2,      # Two spam reports = slash
}


@dataclass
class SlashDecision:
    should_slash: bool
    slash_pct: float          # 0.0 – 1.0
    reason: str
    explanation: str


class SlashingPolicy:
    """
    Evaluates whether a stake should be slashed based on reason and history.

    Args:
        slash_pcts:     Override slash percentages per reason.
        always_slash:   Reasons that always trigger slash (override no_show_count check).
    """

    def __init__(
        self,
        slash_pcts: Optional[dict] = None,
        always_slash: Optional[set] = None,
    ):
        self.slash_pcts = {**_DEFAULT_SLASH_PCT, **(slash_pcts or {})}
        self.always_slash = frozenset(always_slash) if always_slash else _ALWAYS_SLASH

    def slash_amount(self, stake_amount: float, reason: SlashReason) -> float:
        """Return the USDC amount to slash given a stake amount and reason."""
        pct = self.slash_pcts.get(reason, 1.0)
        return round(stake_amount * pct, 6)

    def evaluate(
        self,
        reason: SlashReason,
        no_show_count: int = 0,
        stake_amount: float = 0.0,
    ) -> SlashDecision:
        """
        Decide whether to slash.

        Returns a SlashDecision with should_slash, slash_pct, reason, explanation.
        """
        if reason in self.always_slash:
            pct = self.slash_pcts.get(reason, 1.0)
            return SlashDecision(
                should_slash=True,
                slash_pct=pct,
                reason=reason.value,
                explanation=f"{reason.value} always triggers a {pct*100:.0f}% slash.",
            )

        min_count = _MIN_NO_SHOW_TO_SLASH.get(reason, 1)
        if no_show_count >= min_count:
            pct = self.slash_pcts.get(reason, 1.0)
            return SlashDecision(
                should_slash=True,
                slash_pct=pct,
                reason=reason.value,
                explanation=(
                    f"{reason.value} after {no_show_count} incident(s) "
                    f"triggers a {pct*100:.0f}% slash."
                ),
            )

        return SlashDecision(
            should_slash=False,
            slash_pct=0.0,
            reason=reason.value,
            explanation=(
                f"{reason.value} requires {min_count} incident(s) to slash; "
                f"current count is {no_show_count}."
            ),
        )
