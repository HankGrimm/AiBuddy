"""
Tests for Sprint 5: AI Match Agent
Covers: preference memory, cosine similarity, compatibility scoring,
vibe filters, ranked suggestions, and intro generation.
"""
import uuid
import pytest

from app.models.user import User
from app.models.persona import Persona, IntentMode
from app.models.reputation import ReputationScore
from app.models.block import Block
from app.services.preference_memory_service import PreferenceMemoryService
from app.services.compatibility_scoring_service import CompatibilityScoringService
from app.services.vibe_filter_service import VibeFilterService
from app.services.matchmaking_service import MatchmakingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(db, wallet: str = None) -> User:
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet or f"wallet_{uuid.uuid4().hex[:8]}",
    )
    db.add(user)
    db.flush()
    return user


def make_persona(db, user: User, intent: IntentMode = IntentMode.SOCIAL, room_id=None) -> Persona:
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name=f"persona_{uuid.uuid4().hex[:6]}",
        intent_mode=intent,
        room_id=room_id,
    )
    db.add(p)
    db.flush()
    return p


def make_reputation(db, user: User, composite: float = 75.0, safety: float = 80.0, no_show: float = 0.1) -> ReputationScore:
    rep = ReputationScore(
        id=uuid.uuid4(),
        user_id=user.id,
        composite_score=composite,
        safety_score=safety,
        no_show_rate=no_show,
    )
    db.add(rep)
    db.flush()
    return rep


# ---------------------------------------------------------------------------
# 1. test_store_and_retrieve_preferences
# ---------------------------------------------------------------------------

def test_store_and_retrieve_preferences(db):
    user = make_user(db)
    svc = PreferenceMemoryService(db)

    prefs = {
        "intent_mode": "dating",
        "age_range": {"min": 25, "max": 35},
        "interests": ["music", "travel"],
        "personality_traits": ["adventurous", "creative"],
        "location_range_km": 50.0,
    }
    stored = svc.store(user.id, prefs)

    assert stored.user_id == user.id
    assert stored.intent_mode == "dating"
    assert stored.age_range_min == 25
    assert stored.age_range_max == 35
    assert stored.interests == ["music", "travel"]
    assert stored.location_range_km == 50.0
    assert stored.embedding_vector is not None
    assert len(stored.embedding_vector) > 0

    retrieved = svc.get(user.id)
    assert retrieved is not None
    assert retrieved.user_id == user.id
    assert retrieved.interests == ["music", "travel"]


# ---------------------------------------------------------------------------
# 2. test_cosine_similarity_identical_prefs
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical_prefs(db):
    svc = PreferenceMemoryService(db)

    prefs = {"interests": ["music", "travel"], "personality_traits": ["adventurous"]}
    vec_a = svc.compute_embedding(prefs)
    vec_b = svc.compute_embedding(prefs)

    sim = PreferenceMemoryService.cosine_similarity(vec_a, vec_b)
    assert abs(sim - 1.0) < 1e-6, f"Expected 1.0, got {sim}"


# ---------------------------------------------------------------------------
# 3. test_cosine_similarity_zero_for_opposite
# ---------------------------------------------------------------------------

def test_cosine_similarity_zero_for_opposite(db):
    svc = PreferenceMemoryService(db)

    vec_a = svc.compute_embedding({"interests": ["music"], "personality_traits": []})
    vec_b = svc.compute_embedding({"interests": ["gaming"], "personality_traits": []})

    sim = PreferenceMemoryService.cosine_similarity(vec_a, vec_b)
    # Music and gaming are different vocab entries → zero overlap
    assert sim == 0.0, f"Expected 0.0, got {sim}"


# ---------------------------------------------------------------------------
# 4. test_compatibility_score_higher_same_intent
# ---------------------------------------------------------------------------

def test_compatibility_score_higher_same_intent(db):
    user_a = make_user(db)
    user_same = make_user(db)
    user_diff = make_user(db)

    persona_same = make_persona(db, user_same, intent=IntentMode.DATING)
    persona_diff = make_persona(db, user_diff, intent=IntentMode.NETWORKING)

    make_reputation(db, user_same)
    make_reputation(db, user_diff)

    prefs_a = {"intent_mode": "dating", "interests": ["music"], "personality_traits": []}
    prefs_same = {"intent_mode": "dating", "interests": ["music"], "personality_traits": []}
    prefs_diff = {"intent_mode": "networking", "interests": ["gaming"], "personality_traits": []}

    pref_svc = PreferenceMemoryService(db)
    pref_svc.store(user_a.id, prefs_a)
    pref_svc.store(user_same.id, prefs_same)
    pref_svc.store(user_diff.id, prefs_diff)

    score_svc = CompatibilityScoringService(db)
    bd_same = score_svc.score(user_a.id, persona_same.id)
    bd_diff = score_svc.score(user_a.id, persona_diff.id)

    assert bd_same.total > bd_diff.total, (
        f"Same-intent score {bd_same.total} should be higher than diff-intent {bd_diff.total}"
    )
    assert bd_same.intent_mode_match == 1.0
    assert bd_diff.intent_mode_match == 0.0


# ---------------------------------------------------------------------------
# 5. test_vibe_filter_excludes_low_reputation
# ---------------------------------------------------------------------------

def test_vibe_filter_excludes_low_reputation(db):
    requesting_user = make_user(db)

    user_high = make_user(db)
    user_low = make_user(db)

    persona_high = make_persona(db, user_high)
    persona_low = make_persona(db, user_low)

    make_reputation(db, user_high, composite=80.0)
    make_reputation(db, user_low, composite=30.0)

    vibe_svc = VibeFilterService(db)
    candidates = [persona_high, persona_low]
    filtered = vibe_svc.apply(candidates, {"min_reputation_score": 60.0}, requesting_user.id)

    ids = [p.id for p in filtered]
    assert persona_high.id in ids
    assert persona_low.id not in ids


# ---------------------------------------------------------------------------
# 6. test_vibe_filter_excludes_blocked_users
# ---------------------------------------------------------------------------

def test_vibe_filter_excludes_blocked_users(db):
    requesting_user = make_user(db)
    user_blocked = make_user(db)
    user_ok = make_user(db)

    persona_blocked = make_persona(db, user_blocked)
    persona_ok = make_persona(db, user_ok)

    block = Block(
        id=uuid.uuid4(),
        blocker_id=requesting_user.id,
        blocked_id=user_blocked.id,
    )
    db.add(block)
    db.flush()

    vibe_svc = VibeFilterService(db)
    candidates = [persona_blocked, persona_ok]
    filtered = vibe_svc.apply(candidates, {"exclude_blocked": True}, requesting_user.id)

    ids = [p.id for p in filtered]
    assert persona_ok.id in ids
    assert persona_blocked.id not in ids


# ---------------------------------------------------------------------------
# 7. test_suggestions_ranked_by_score
# ---------------------------------------------------------------------------

def test_suggestions_ranked_by_score(db):
    user_a = make_user(db)

    # User with matching intent + great reputation → high score
    user_good = make_user(db)
    persona_good = make_persona(db, user_good, intent=IntentMode.DATING)
    make_reputation(db, user_good, composite=90.0)

    # User with matching intent but slightly lower reputation → lower score
    user_ok = make_user(db)
    persona_ok = make_persona(db, user_ok, intent=IntentMode.DATING)
    make_reputation(db, user_ok, composite=55.0)

    pref_svc = PreferenceMemoryService(db)
    pref_svc.store(user_a.id, {"intent_mode": "dating", "interests": ["music"], "personality_traits": ["adventurous"]})
    pref_svc.store(user_good.id, {"intent_mode": "dating", "interests": ["music"], "personality_traits": ["adventurous"]})
    pref_svc.store(user_ok.id, {"intent_mode": "dating", "interests": ["music"], "personality_traits": []})

    svc = MatchmakingService(db)
    user_a_obj = db.query(User).filter(User.id == user_a.id).first()
    suggestions = svc.get_suggestions(user_a_obj, limit=10)

    assert len(suggestions) >= 2
    scores = [s["compatibility_score"] for s in suggestions]
    # Verify sorted descending
    assert scores == sorted(scores, reverse=True), f"Scores not sorted: {scores}"

    # The good persona should rank first (highest score)
    ids = [s["persona_id"] for s in suggestions]
    assert ids[0] == persona_good.id, f"Expected persona_good first, got {ids}"


# ---------------------------------------------------------------------------
# 8. test_intro_generation_returns_string
# ---------------------------------------------------------------------------

def test_intro_generation_returns_string(db):
    user_a = make_user(db)
    user_b = make_user(db)
    persona_b = make_persona(db, user_b, intent=IntentMode.SOCIAL)

    pref_svc = PreferenceMemoryService(db)
    pref_svc.store(user_a.id, {"interests": ["music", "travel"], "personality_traits": []})
    pref_svc.store(user_b.id, {"interests": ["music", "hiking"], "personality_traits": []})

    svc = MatchmakingService(db)
    user_a_obj = db.query(User).filter(User.id == user_a.id).first()
    result = svc.generate_intro(user_a_obj, persona_b.id, context="Met at the Sol conference")

    assert isinstance(result["intro"], str)
    assert len(result["intro"]) > 10
    assert str(persona_b.id) == result["target_persona_id"]
    # Shared interest 'music' should appear in intro
    assert "music" in result["intro"]
