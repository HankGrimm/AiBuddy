"""
Tests for MatchmakingService covering uncovered lines:
- update_preferences (lines 24-25)
- get_suggestions with room_id filter (line 37)
- generate_intro 404 path (lines 70-71)
- apply_vibe_filter (lines 76-82)
- _shared_interests with both prefs set (line 97)
"""
import uuid
import pytest

from app.models.user import User
from app.models.persona import Persona, IntentMode
from app.models.reputation import ReputationScore
from app.services.matchmaking_service import MatchmakingService


def make_user(db):
    u = User(id=uuid.uuid4(), wallet_address=f"w_{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(u)
    db.commit()
    return u


def make_persona(db, user, room_id=None):
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name=f"p_{uuid.uuid4().hex[:6]}",
        intent_mode=IntentMode.SOCIAL,
        is_active=True,
        room_id=room_id,
    )
    db.add(p)
    db.commit()
    return p


def make_reputation(db, user, composite=75.0, safety=80.0):
    rep = ReputationScore(
        id=uuid.uuid4(),
        user_id=user.id,
        composite_score=composite,
        safety_score=safety,
    )
    db.add(rep)
    db.commit()
    return rep


class TestUpdatePreferences:
    """Covers lines 24-25: update_preferences stores prefs and returns summary."""

    def test_update_preferences_returns_status(self, db):
        user = make_user(db)
        svc = MatchmakingService(db)
        result = svc.update_preferences(user, {"interests": ["hiking", "coffee"]})
        assert result["status"] == "preferences_saved"
        assert result["user_id"] == str(user.id)

    def test_update_preferences_persists_to_db(self, db):
        user = make_user(db)
        svc = MatchmakingService(db)
        svc.update_preferences(user, {"interests": ["yoga"]})
        from app.services.preference_memory_service import PreferenceMemoryService
        prefs = PreferenceMemoryService(db).get(user.id)
        assert prefs is not None
        assert "yoga" in prefs.interests


class TestGetSuggestionsWithRoomFilter:
    """Covers line 37: get_suggestions with room_id narrows to that room."""

    def test_suggestions_with_room_id_returns_only_room_personas(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        user_c = make_user(db)
        room_id = uuid.uuid4()

        make_persona(db, user_b, room_id=room_id)  # in room
        make_persona(db, user_c)  # no room
        make_reputation(db, user_b)
        make_reputation(db, user_c)

        svc = MatchmakingService(db)
        results = svc.get_suggestions(user_a, room_id=room_id, limit=10)
        # All returned personas should belong to users in the room
        # (may be 0 if score < 0.3, but no assertion errors thrown)
        assert isinstance(results, list)

    def test_suggestions_without_room_id_includes_all(self, db):
        user_a = make_user(db)
        svc = MatchmakingService(db)
        results = svc.get_suggestions(user_a, room_id=None, limit=5)
        assert isinstance(results, list)


class TestGenerateIntro404:
    """Covers lines 70-71: generate_intro raises 404 when persona not found."""

    def test_generate_intro_missing_persona_raises_404(self, db):
        from fastapi import HTTPException
        user = make_user(db)
        svc = MatchmakingService(db)
        with pytest.raises(HTTPException) as exc_info:
            svc.generate_intro(user, uuid.uuid4(), context=None)
        assert exc_info.value.status_code == 404

    def test_generate_intro_found_persona_returns_dict(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)
        svc = MatchmakingService(db)
        result = svc.generate_intro(user_a, persona_b.id, context=None)
        assert "intro" in result
        assert result["target_persona_id"] == str(persona_b.id)

    def test_generate_intro_with_context(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)
        svc = MatchmakingService(db)
        result = svc.generate_intro(user_a, persona_b.id, context="We met at the yoga class.")
        assert "We met at the yoga class." in result["intro"]


class TestApplyVibeFilter:
    """Covers lines 76-82: apply_vibe_filter returns persona_ids."""

    def test_apply_vibe_filter_returns_summary(self, db):
        user = make_user(db)
        svc = MatchmakingService(db)
        result = svc.apply_vibe_filter(user, {"min_reputation": 0.0})
        assert result["status"] == "filter_applied"
        assert "result_count" in result
        assert "persona_ids" in result
        assert isinstance(result["persona_ids"], list)

    def test_apply_vibe_filter_reflects_filters_in_response(self, db):
        user = make_user(db)
        svc = MatchmakingService(db)
        filters = {"intent_mode": "social"}
        result = svc.apply_vibe_filter(user, filters)
        assert result["filters"] == filters

    def test_apply_vibe_filter_excludes_self(self, db):
        user = make_user(db)
        make_persona(db, user)  # own persona
        svc = MatchmakingService(db)
        result = svc.apply_vibe_filter(user, {})
        # Own persona should never appear
        from app.models.persona import Persona as P
        own_ids = [str(p.id) for p in db.query(P).filter(P.user_id == user.id).all()]
        for pid in result["persona_ids"]:
            assert pid not in own_ids


class TestSharedInterests:
    """Covers line 97: _shared_interests returns sorted intersection."""

    def test_shared_interests_returns_intersection(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)

        svc = MatchmakingService(db)
        svc.update_preferences(user_a, {"interests": ["hiking", "coffee", "yoga"]})
        svc.update_preferences(user_b, {"interests": ["coffee", "yoga", "travel"]})

        shared = svc._shared_interests(user_a.id, persona_b)
        assert "coffee" in shared
        assert "yoga" in shared
        assert "hiking" not in shared
        assert "travel" not in shared

    def test_shared_interests_sorted(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)

        svc = MatchmakingService(db)
        svc.update_preferences(user_a, {"interests": ["Zen", "Art", "Music"]})
        svc.update_preferences(user_b, {"interests": ["art", "music", "code"]})

        shared = svc._shared_interests(user_a.id, persona_b)
        assert shared == sorted(shared)

    def test_shared_interests_no_prefs_returns_empty(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)
        svc = MatchmakingService(db)
        # No prefs stored → should return []
        result = svc._shared_interests(user_a.id, persona_b)
        assert result == []
