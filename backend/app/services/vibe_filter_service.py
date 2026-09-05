"""
Vibe Filter Service — filters a list of Persona candidates based on
safety thresholds, intent requirements, and block lists.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.block import Block
from ..models.persona import Persona
from ..models.reputation import ReputationScore


class VibeFilterService:
    def __init__(self, db: Session):
        self.db = db

    def apply(
        self,
        candidates: List[Persona],
        filters: dict,
        requesting_user_id: UUID,
    ) -> List[Persona]:
        """
        Return the subset of *candidates* that pass all active filters.

        Supported filter keys:
          - min_reputation_score (float, 0-100)
          - max_no_show_rate     (float, 0-1)
          - required_intent_mode (str)
          - exclude_blocked      (bool, default True)
        """
        min_rep: Optional[float] = filters.get("min_reputation_score")
        max_no_show: Optional[float] = filters.get("max_no_show_rate")
        required_intent: Optional[str] = filters.get("required_intent_mode")
        exclude_blocked: bool = filters.get("exclude_blocked", True)

        # Pre-fetch blocked user IDs (users blocked by the requester)
        blocked_ids: set[UUID] = set()
        if exclude_blocked:
            rows = (
                self.db.query(Block.blocked_id)
                .filter(Block.blocker_id == requesting_user_id)
                .all()
            )
            blocked_ids = {r[0] for r in rows}

        # Pre-fetch reputation rows for candidate users
        candidate_user_ids = [p.user_id for p in candidates]
        rep_map: dict[UUID, ReputationScore] = {}
        if candidate_user_ids and (min_rep is not None or max_no_show is not None):
            reps = (
                self.db.query(ReputationScore)
                .filter(ReputationScore.user_id.in_(candidate_user_ids))
                .all()
            )
            rep_map = {r.user_id: r for r in reps}

        result: List[Persona] = []
        for persona in candidates:
            # Block filter
            if exclude_blocked and persona.user_id in blocked_ids:
                continue

            # Intent mode filter
            if required_intent and persona.intent_mode.value != required_intent:
                continue

            # Reputation filters
            if min_rep is not None or max_no_show is not None:
                rep = rep_map.get(persona.user_id)
                if rep is None:
                    # No reputation record → treat as neutral (50.0 score, 0 no-shows)
                    rep_score = 50.0
                    no_show = 0.0
                else:
                    rep_score = rep.composite_score
                    no_show = rep.no_show_rate

                if min_rep is not None and rep_score < min_rep:
                    continue
                if max_no_show is not None and no_show > max_no_show:
                    continue

            result.append(persona)

        return result
