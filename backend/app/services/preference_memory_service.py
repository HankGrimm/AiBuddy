"""
Preference Memory Service — stores and retrieves user preferences,
computes semantic embeddings, and provides cosine similarity.

Primary: 768-dim BAAI/bge embeddings via AINative /zerodb/embed (16ms inference)
Fallback: pure-Python bag-of-words (45-term vocab, L2-normalised) when unconfigured

The fallback ensures all tests pass and the API runs without external keys.
"""
from __future__ import annotations

import math
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.match_agent import UserPreferences
from .ainative_service import embed_preferences, upsert_preference_vector, _is_configured as _ainative_configured


# ---------------------------------------------------------------------------
# Fallback: bag-of-words vocabulary (used when AINative not configured)
# ---------------------------------------------------------------------------

_VOCAB: list[str] = [
    # interests
    "music", "travel", "hiking", "cooking", "gaming", "art", "sports",
    "fitness", "reading", "photography", "yoga", "dancing", "coffee",
    "tech", "science", "nature", "movies", "anime", "food", "fashion",
    "startup", "crypto", "blockchain", "defi", "monad",
    # personality traits
    "adventurous", "creative", "ambitious", "empathetic", "humorous",
    "introverted", "extroverted", "caring", "intellectual", "spiritual",
    "optimistic", "spontaneous", "reliable", "passionate", "laid_back",
    "social", "independent", "romantic", "playful", "serious",
]
_VOCAB_INDEX: dict[str, int] = {w: i for i, w in enumerate(_VOCAB)}


def _normalise(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0.0:
        return vec
    return [x / mag for x in vec]


def _bow_embedding(prefs: dict) -> list[float]:
    """Fallback: bag-of-words vector over fixed 45-term vocabulary."""
    vec = [0.0] * len(_VOCAB)
    for term in prefs.get("interests", []) or []:
        key = term.lower().replace(" ", "_")
        if key in _VOCAB_INDEX:
            vec[_VOCAB_INDEX[key]] += 1.0
    for term in prefs.get("personality_traits", []) or []:
        key = term.lower().replace(" ", "_")
        if key in _VOCAB_INDEX:
            vec[_VOCAB_INDEX[key]] += 1.0
    return _normalise(vec)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class PreferenceMemoryService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, user_id: UUID, prefs: dict) -> UserPreferences:
        """Upsert user preferences and recompute the embedding vector."""
        embedding = self.compute_embedding(prefs)

        existing = self.db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()

        if existing:
            existing.intent_mode = prefs.get("intent_mode", existing.intent_mode)
            age = prefs.get("age_range", {})
            if age:
                existing.age_range_min = age.get("min", existing.age_range_min)
                existing.age_range_max = age.get("max", existing.age_range_max)
            if "interests" in prefs:
                existing.interests = prefs["interests"]
            if "dealbreakers" in prefs:
                existing.dealbreakers = prefs["dealbreakers"]
            if "location_range_km" in prefs:
                existing.location_range_km = prefs["location_range_km"]
            if "personality_traits" in prefs:
                existing.personality_traits = prefs["personality_traits"]
            existing.embedding_vector = embedding
            self.db.commit()
            self.db.refresh(existing)
            # Also sync to ZeroDB vector store for cross-user semantic search
            self._sync_to_zerodb(user_id, embedding, prefs)
            return existing

        age = prefs.get("age_range", {})
        record = UserPreferences(
            user_id=user_id,
            intent_mode=prefs.get("intent_mode"),
            age_range_min=age.get("min") if age else None,
            age_range_max=age.get("max") if age else None,
            interests=prefs.get("interests"),
            dealbreakers=prefs.get("dealbreakers"),
            location_range_km=prefs.get("location_range_km"),
            personality_traits=prefs.get("personality_traits"),
            embedding_vector=embedding,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        self._sync_to_zerodb(user_id, embedding, prefs)
        return record

    def get(self, user_id: UUID) -> Optional[UserPreferences]:
        return (
            self.db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )

    def compute_embedding(self, prefs: dict) -> list[float]:
        """
        Compute preference embedding.
        - AINative configured: 768-dim BAAI/bge semantic vector (16ms, free tier)
        - Fallback: 45-dim bag-of-words keyword vector (zero dependencies)
        """
        if _ainative_configured():
            return embed_preferences(
                interests=prefs.get("interests") or [],
                personality_traits=prefs.get("personality_traits") or [],
            )
        return _bow_embedding(prefs)

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Return cosine similarity in [0, 1] between two pre-normalised vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        # Clamp to [0, 1] — vectors are normalised so dot ≈ cosine
        return max(0.0, min(1.0, dot))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sync_to_zerodb(self, user_id: UUID, embedding: list[float], prefs: dict) -> None:
        """Best-effort: push preference vector to ZeroDB for cross-user semantic search."""
        interests = prefs.get("interests") or []
        traits = prefs.get("personality_traits") or []
        profile_text = "Interests: " + ", ".join(interests)
        if traits:
            profile_text += ". Personality: " + ", ".join(traits)

        upsert_preference_vector(
            user_id=str(user_id),
            embedding=embedding,
            metadata={
                "intent_mode": prefs.get("intent_mode"),
                "profile_text": profile_text,
                "interests": interests,
                "personality_traits": traits,
            },
        )
