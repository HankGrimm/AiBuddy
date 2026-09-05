"""
Compatibility Scoring Service — produces a structured breakdown of how
well two users / personas are likely to match.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.persona import Persona
from ..models.reputation import ReputationScore
from .preference_memory_service import PreferenceMemoryService


@dataclass
class CompatibilityBreakdown:
    user_a_id: str
    persona_b_id: str
    preference_similarity: float = 0.0   # 0-1: embedding cosine similarity
    room_context_match: float = 0.0      # 0-1: shared room / intent alignment
    intent_mode_match: float = 0.0       # 0 or 1: exact intent match
    reputation_trust_score: float = 0.0  # 0-1: normalised composite reputation
    behavioral_safety_score: float = 0.0 # 0-1: low no-show rate + high safety score
    total: float = 0.0                   # weighted aggregate

    # Weights (must sum to 1.0)
    _W_PREF: float = field(default=0.35, init=False, repr=False)
    _W_ROOM: float = field(default=0.15, init=False, repr=False)
    _W_INTENT: float = field(default=0.20, init=False, repr=False)
    _W_REP: float = field(default=0.20, init=False, repr=False)
    _W_SAFETY: float = field(default=0.10, init=False, repr=False)

    def recompute_total(self) -> None:
        self.total = round(
            self.preference_similarity * self._W_PREF
            + self.room_context_match * self._W_ROOM
            + self.intent_mode_match * self._W_INTENT
            + self.reputation_trust_score * self._W_REP
            + self.behavioral_safety_score * self._W_SAFETY,
            4,
        )


class CompatibilityScoringService:
    def __init__(self, db: Session):
        self.db = db
        self._pref_svc = PreferenceMemoryService(db)

    def score(self, user_a_id: UUID, persona_b_id: UUID) -> CompatibilityBreakdown:
        breakdown = CompatibilityBreakdown(
            user_a_id=str(user_a_id),
            persona_b_id=str(persona_b_id),
        )

        persona_b = self.db.query(Persona).filter(Persona.id == persona_b_id).first()
        if not persona_b:
            return breakdown

        # --- Preference similarity (embedding cosine) ---
        prefs_a = self._pref_svc.get(user_a_id)
        prefs_b = self._pref_svc.get(persona_b.user_id)

        if (
            prefs_a
            and prefs_b
            and prefs_a.embedding_vector
            and prefs_b.embedding_vector
        ):
            breakdown.preference_similarity = PreferenceMemoryService.cosine_similarity(
                prefs_a.embedding_vector, prefs_b.embedding_vector
            )

        # --- Intent mode match ---
        if prefs_a and prefs_a.intent_mode:
            if persona_b.intent_mode.value == prefs_a.intent_mode:
                breakdown.intent_mode_match = 1.0
            else:
                breakdown.intent_mode_match = 0.0
        else:
            # No stated preference — neutral
            breakdown.intent_mode_match = 0.5

        # --- Room context match ---
        # Full credit if persona B is in a room; partial if public
        if persona_b.room_id:
            breakdown.room_context_match = 0.8
        else:
            breakdown.room_context_match = 0.4

        # --- Reputation trust score ---
        rep_b = (
            self.db.query(ReputationScore)
            .filter(ReputationScore.user_id == persona_b.user_id)
            .first()
        )
        if rep_b:
            breakdown.reputation_trust_score = min(1.0, rep_b.composite_score / 100.0)
        else:
            breakdown.reputation_trust_score = 0.5  # default neutral

        # --- Behavioral safety score ---
        if rep_b:
            # Higher safety_score (0-100) + low no_show_rate → better score
            safety_norm = min(1.0, rep_b.safety_score / 100.0)
            no_show_penalty = min(1.0, rep_b.no_show_rate)  # rate is 0-1
            breakdown.behavioral_safety_score = max(0.0, safety_norm - no_show_penalty * 0.5)
        else:
            breakdown.behavioral_safety_score = 0.5

        breakdown.recompute_total()
        return breakdown
