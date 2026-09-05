"""
Slashing Policy Service

Evaluates safety-escrow slashing decisions based on no-shows, harassment reports,
and false reporting. Also manages DM suspension thresholds and stake multipliers.
"""
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from ..models.stake import Stake, StakeStatus, StakeType
from ..models.report import Report, ReportType


@dataclass
class SlashDecision:
    """Result returned by every evaluate_* method."""
    should_slash: bool
    slash_amount_usdc: float
    reason: str
    penalty_pct: float = 1.0  # fraction of stake to slash (0.0–1.0)
    notes: str = ""


# Thresholds — kept as module-level constants so they can be patched in tests
NO_SHOW_SUSPEND_THRESHOLD: int = 3       # no-shows before DM suspension
MULTIPLIER_BASE: float = 1.0             # baseline stake multiplier
MULTIPLIER_INCREMENT: float = 0.5        # added per no-show event
MULTIPLIER_CLAMP: float = 3.0            # maximum multiplier
HARASSMENT_SLASH_PCT: float = 1.0        # 100 % slash on confirmed harassment
FALSE_REPORT_SLASH_PCT: float = 0.5      # 50 % slash on confirmed false report


class SlashingPolicyService:
    """
    Evaluates whether a stake should be slashed and by how much.

    All evaluate_* methods are *pure policy* — they do **not** write to the DB.
    The caller (StakeService / a Celery task) is responsible for persisting results.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate_no_show(self, stake: Stake) -> SlashDecision:
        """
        Called when a meetup initiator or confirmed attendee did not show up.

        The full stake amount is slashed. Repeated offenders get a higher
        multiplier applied to future stakes (see get_stake_multiplier).
        """
        if stake.status not in (StakeStatus.ACTIVE, StakeStatus.PENDING):
            return SlashDecision(
                should_slash=False,
                slash_amount_usdc=0.0,
                reason="Stake is not in a slashable state",
                penalty_pct=0.0,
            )

        multiplier = self.get_stake_multiplier(stake.user_id)
        slash_amount = stake.amount_usdc  # full stake slashed for no-show

        return SlashDecision(
            should_slash=True,
            slash_amount_usdc=slash_amount,
            reason="No-show: meetup commitment not honoured",
            penalty_pct=1.0,
            notes=f"Stake multiplier for future stakes: {multiplier}",
        )

    def evaluate_harassment(self, report: Report, stake: Stake) -> SlashDecision:
        """
        Called when a harassment report is confirmed against the stake owner.

        100 % of the stake is slashed.
        """
        if stake.status not in (StakeStatus.ACTIVE, StakeStatus.PENDING):
            return SlashDecision(
                should_slash=False,
                slash_amount_usdc=0.0,
                reason="Stake is not in a slashable state",
                penalty_pct=0.0,
            )

        if report.report_type not in (ReportType.HARASSMENT,):
            return SlashDecision(
                should_slash=False,
                slash_amount_usdc=0.0,
                reason="Report type does not trigger harassment slashing",
                penalty_pct=0.0,
            )

        slash_amount = round(stake.amount_usdc * HARASSMENT_SLASH_PCT, 6)

        return SlashDecision(
            should_slash=True,
            slash_amount_usdc=slash_amount,
            reason=f"Confirmed harassment report #{report.id}",
            penalty_pct=HARASSMENT_SLASH_PCT,
            notes=f"Report description: {report.description[:120]}",
        )

    def evaluate_false_report(self, report: Report) -> SlashDecision:
        """
        Called when a report filed by a user is confirmed to be false.

        The *reporter's* active DM or meetup stake is identified and 50 % slashed.
        Because the reporter's stake is not passed directly here we return a
        SlashDecision with the penalty percentage; the caller resolves the stake.
        """
        if report.report_type != ReportType.FALSE_REPORTING:
            # Any report type can be determined to be false; use the generic path
            pass

        return SlashDecision(
            should_slash=True,
            slash_amount_usdc=0.0,  # caller must multiply by reporter's stake amount
            reason=f"False report filed against user {report.reported_user_id}",
            penalty_pct=FALSE_REPORT_SLASH_PCT,
            notes="50 % of reporter's active stake will be slashed",
        )

    def should_suspend_dm(self, user_id: UUID) -> bool:
        """
        Returns True when the user has accumulated 3+ no-show slash events,
        indicating their DM privileges should be suspended.
        """
        no_show_count = (
            self.db.query(Stake)
            .filter(
                Stake.user_id == user_id,
                Stake.status == StakeStatus.SLASHED,
                Stake.slash_reason.ilike("%no-show%"),
            )
            .count()
        )
        return no_show_count >= NO_SHOW_SUSPEND_THRESHOLD

    def get_stake_multiplier(self, user_id: UUID) -> float:
        """
        Returns a multiplier > 1.0 for repeat no-show offenders so that the
        minimum required stake increases with each violation.

        multiplier = 1.0 + (no_show_count * 0.5), clamped at 3.0.
        """
        no_show_count = (
            self.db.query(Stake)
            .filter(
                Stake.user_id == user_id,
                Stake.status == StakeStatus.SLASHED,
                Stake.slash_reason.ilike("%no-show%"),
            )
            .count()
        )
        raw = MULTIPLIER_BASE + (no_show_count * MULTIPLIER_INCREMENT)
        return min(raw, MULTIPLIER_CLAMP)
