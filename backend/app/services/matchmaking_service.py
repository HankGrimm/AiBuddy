from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List, Dict, Any

from ..models.persona import Persona
from ..models.user import User
from .preference_memory_service import PreferenceMemoryService
from .compatibility_scoring_service import CompatibilityScoringService
from .vibe_filter_service import VibeFilterService
from .ainative_service import generate_match_intro


class MatchmakingService:
    def __init__(self, db: Session):
        self.db = db
        self._pref_svc = PreferenceMemoryService(db)
        self._score_svc = CompatibilityScoringService(db)
        self._vibe_svc = VibeFilterService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_preferences(self, user: User, prefs: Dict[str, Any]) -> dict:
        record = self._pref_svc.store(user.id, prefs)
        return {"status": "preferences_saved", "user_id": str(user.id)}

    def get_suggestions(
        self, user: User, room_id: Optional[UUID] = None, limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[dict]:
        # Fetch candidate personas
        q = self.db.query(Persona).filter(
            Persona.is_active == True,
            Persona.user_id != user.id,
        )
        if room_id:
            q = q.filter(Persona.room_id == room_id)
        candidates = q.limit(100).all()

        # Apply vibe filter
        active_filters = filters or {}
        candidates = self._vibe_svc.apply(candidates, active_filters, user.id)

        # Score and rank
        suggestions = []
        for persona in candidates:
            breakdown = self._score_svc.score(user.id, persona.id)
            if breakdown.total > 0.3:
                suggestions.append({
                    "persona_id": persona.id,
                    "compatibility_score": breakdown.total,
                    "intro_suggestion": self._generate_intro_text(user, persona),
                    "shared_interests": self._shared_interests(user.id, persona),
                    "room_context": str(room_id) if room_id else None,
                    "breakdown": {
                        "preference_similarity": breakdown.preference_similarity,
                        "room_context_match": breakdown.room_context_match,
                        "intent_mode_match": breakdown.intent_mode_match,
                        "reputation_trust_score": breakdown.reputation_trust_score,
                        "behavioral_safety_score": breakdown.behavioral_safety_score,
                    },
                })

        suggestions.sort(key=lambda x: x["compatibility_score"], reverse=True)
        return suggestions[:limit]

    def generate_intro(self, user: User, target_persona_id: UUID, context: Optional[str]) -> dict:
        target = self.db.query(Persona).filter(Persona.id == target_persona_id).first()
        if not target:
            from fastapi import HTTPException
            raise HTTPException(404, "Target persona not found")
        intro = self._generate_intro_text(user, target, context)
        return {"intro": intro, "target_persona_id": str(target_persona_id)}

    def apply_vibe_filter(self, user: User, filters: Dict[str, Any]) -> dict:
        q = self.db.query(Persona).filter(
            Persona.is_active == True,
            Persona.user_id != user.id,
        )
        candidates = q.limit(200).all()
        filtered = self._vibe_svc.apply(candidates, filters, user.id)
        return {
            "status": "filter_applied",
            "filters": filters,
            "result_count": len(filtered),
            "persona_ids": [str(p.id) for p in filtered],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _shared_interests(self, user_id: UUID, persona: Persona) -> List[str]:
        prefs_a = self._pref_svc.get(user_id)
        prefs_b = self._pref_svc.get(persona.user_id)
        if not prefs_a or not prefs_b:
            return []
        a_set = set(i.lower() for i in (prefs_a.interests or []))
        b_set = set(i.lower() for i in (prefs_b.interests or []))
        return sorted(a_set & b_set)

    def _generate_intro_text(
        self, user: User, persona: Persona, context: Optional[str] = None
    ) -> str:
        prefs = self._pref_svc.get(user.id)
        shared = self._shared_interests(user.id, persona)
        intent = prefs.intent_mode if prefs else None

        # Use AINative LLM for personalised intro; falls back to template if unconfigured
        return generate_match_intro(
            requester_name=user.wallet_address[:8] + "...",
            target_name=persona.display_name or "there",
            shared_interests=shared,
            requester_intent=intent,
            context=context,
        )
