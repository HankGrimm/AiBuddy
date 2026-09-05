"""
Coverage for PreferenceMemoryService — store, get, compute_embedding,
cosine_similarity, and the upsert (update) path.
"""
import uuid
import math

import pytest

from app.models.user import User
from app.services.preference_memory_service import PreferenceMemoryService, _VOCAB


def _user(db) -> User:
    u = User(id=uuid.uuid4(), wallet_address=f"w_{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(u)
    db.commit()
    return u


# ── compute_embedding ─────────────────────────────────────────────────────────

def test_embedding_length_matches_vocab(db):
    svc = PreferenceMemoryService(db)
    vec = svc.compute_embedding({"interests": ["music"], "personality_traits": []})
    assert len(vec) == len(_VOCAB)


def test_embedding_is_normalised(db):
    svc = PreferenceMemoryService(db)
    vec = svc.compute_embedding({"interests": ["music", "travel", "gaming"]})
    magnitude = math.sqrt(sum(x * x for x in vec))
    assert abs(magnitude - 1.0) < 1e-6


def test_embedding_empty_prefs_all_zeros(db):
    svc = PreferenceMemoryService(db)
    vec = svc.compute_embedding({})
    assert all(v == 0.0 for v in vec)


def test_embedding_unknown_terms_ignored(db):
    svc = PreferenceMemoryService(db)
    vec = svc.compute_embedding({"interests": ["__notaword__", "???"]})
    assert all(v == 0.0 for v in vec)


def test_embedding_case_insensitive(db):
    svc = PreferenceMemoryService(db)
    vec_lower = svc.compute_embedding({"interests": ["music"]})
    vec_upper = svc.compute_embedding({"interests": ["MUSIC"]})
    assert vec_lower == vec_upper


def test_embedding_personality_traits_included(db):
    svc = PreferenceMemoryService(db)
    vec = svc.compute_embedding({"personality_traits": ["adventurous"]})
    # Should be non-zero (adventurous is in vocab)
    assert any(v > 0 for v in vec)


# ── cosine_similarity ─────────────────────────────────────────────────────────

def test_cosine_similarity_identical_vectors(db):
    svc = PreferenceMemoryService(db)
    vec = svc.compute_embedding({"interests": ["music", "travel"]})
    assert PreferenceMemoryService.cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-5)


def test_cosine_similarity_orthogonal_vectors():
    # Two non-overlapping interests → similarity = 0
    n = len(_VOCAB)
    a = [0.0] * n
    b = [0.0] * n
    a[0] = 1.0
    b[1] = 1.0
    assert PreferenceMemoryService.cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)


def test_cosine_similarity_empty_vectors():
    assert PreferenceMemoryService.cosine_similarity([], []) == 0.0


def test_cosine_similarity_mismatched_lengths():
    assert PreferenceMemoryService.cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_cosine_similarity_partial_overlap(db):
    svc = PreferenceMemoryService(db)
    a = svc.compute_embedding({"interests": ["music", "travel"]})
    b = svc.compute_embedding({"interests": ["music", "gaming"]})
    sim = PreferenceMemoryService.cosine_similarity(a, b)
    assert 0.0 < sim < 1.0


# ── store / get ───────────────────────────────────────────────────────────────

def test_store_creates_new_preferences(db):
    user = _user(db)
    svc = PreferenceMemoryService(db)

    prefs = svc.store(user.id, {
        "intent_mode": "dating",
        "interests": ["music", "travel"],
        "personality_traits": ["adventurous"],
        "age_range": {"min": 25, "max": 35},
    })

    assert prefs.user_id == user.id
    assert prefs.intent_mode == "dating"
    assert "music" in prefs.interests
    assert len(prefs.embedding_vector) == len(_VOCAB)


def test_store_upserts_on_second_call(db):
    user = _user(db)
    svc = PreferenceMemoryService(db)

    svc.store(user.id, {"intent_mode": "social", "interests": ["music"]})
    updated = svc.store(user.id, {"intent_mode": "dating", "interests": ["gaming"]})

    assert updated.intent_mode == "dating"
    assert "gaming" in updated.interests

    # Only one record should exist
    from app.models.match_agent import UserPreferences
    count = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).count()
    assert count == 1


def test_get_returns_none_for_unknown_user(db):
    svc = PreferenceMemoryService(db)
    assert svc.get(uuid.uuid4()) is None


def test_get_returns_stored_preferences(db):
    user = _user(db)
    svc = PreferenceMemoryService(db)
    svc.store(user.id, {"interests": ["yoga"]})

    fetched = svc.get(user.id)
    assert fetched is not None
    assert "yoga" in fetched.interests


def test_store_updates_dealbreakers_and_location(db):
    user = _user(db)
    svc = PreferenceMemoryService(db)
    svc.store(user.id, {"interests": ["yoga"]})
    updated = svc.store(user.id, {
        "dealbreakers": ["smoking"],
        "location_range_km": 25.0,
        "personality_traits": ["creative"],
    })
    assert updated.dealbreakers == ["smoking"]
    assert updated.location_range_km == pytest.approx(25.0)
