"""
Time-based reputation decay.

Applies -1pt/week to each active dimension for users who have been inactive.
Designed to be called from a Celery beat task or cron job.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional

from .scoring import ReputationDimensions

_DECAY_PER_WEEK = 1.0
_DECAY_DIMENSIONS = ["reliability", "response_rate", "meetup_completion"]
_MIN_VALUE = 10.0  # Floor: decay stops at 10


def apply_decay(
    score: ReputationDimensions,
    last_active: datetime,
    now: Optional[datetime] = None,
) -> ReputationDimensions:
    """
    Apply time-proportional decay to a reputation score.

    Decay rate: -1pt/week per dimension, floor at 10.
    Only affects reliability, response_rate, meetup_completion (not safety/consent).

    Args:
        score:       Current reputation dimensions.
        last_active: Last time the user was active.
        now:         Current time (defaults to utcnow).

    Returns:
        Updated ReputationDimensions with decay applied.
    """
    now = now or datetime.utcnow()
    weeks_inactive = (now - last_active).total_seconds() / (7 * 24 * 3600)

    if weeks_inactive < 1.0:
        return score  # No decay for less than 1 week

    decay = round(weeks_inactive * _DECAY_PER_WEEK, 2)

    for dim in _DECAY_DIMENSIONS:
        current = getattr(score, dim, 50.0)
        new_val = max(_MIN_VALUE, current - decay)
        setattr(score, dim, new_val)

    return score.clamp()


def bulk_decay(
    users: Iterable[tuple],  # (user_id, ReputationDimensions, last_active: datetime)
    on_update: Callable,      # callback(user_id, updated_score)
    days_inactive_threshold: int = 7,
    now: Optional[datetime] = None,
) -> int:
    """
    Apply decay to a batch of users.

    Args:
        users:                     Iterable of (user_id, score, last_active) tuples.
        on_update:                 Called with (user_id, updated_score) for each decayed user.
        days_inactive_threshold:   Skip users active within this many days.
        now:                       Current time (defaults to utcnow).

    Returns:
        Number of users whose scores were updated.
    """
    now = now or datetime.utcnow()
    threshold = now - timedelta(days=days_inactive_threshold)
    updated = 0

    for user_id, score, last_active in users:
        if last_active and last_active < threshold:
            updated_score = apply_decay(score, last_active, now)
            on_update(user_id, updated_score)
            updated += 1

    return updated


