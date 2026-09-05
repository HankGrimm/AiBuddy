"""
Tests for ZeroDBClient and AINativeService.

Covers:
- ZeroDBClient stub mode (no credentials)
- ZeroDBClient live mode: store, search, moderation enqueue
- AINativeService stub mode (no credentials)
- AINativeService: generate_match_intro (chat completions)
- AINativeService: embed_preferences (ZeroDB embed)
- AINativeService: search_similar_profiles (ZeroDB vector search)
- AINativeService: moderate_message (chat completions)

Refs #6
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ── ZeroDBClient ─────────────────────────────────────────────────────────────

class TestZeroDBClientStubMode:
    """When credentials are absent, all methods are no-ops."""

    def setup_method(self):
        import os
        for k in ("ZERODB_API_KEY", "ZERODB_PROJECT_ID"):
            os.environ.pop(k, None)

    def test_store_preference_returns_none(self):
        from app.services.zerodb_client import ZeroDBClient
        result = ZeroDBClient().store_preference_embedding(
            user_id=uuid.uuid4(),
            embedding=[0.1] * 768,
            metadata={"intent": "dating"},
        )
        assert result is None

    def test_search_returns_empty_list(self):
        from app.services.zerodb_client import ZeroDBClient
        result = ZeroDBClient().search_similar_preferences([0.1] * 768, limit=5)
        assert result == []

    def test_enqueue_moderation_returns_none(self):
        from app.services.zerodb_client import ZeroDBClient
        result = ZeroDBClient().enqueue_moderation_item(
            item_id=uuid.uuid4(),
            category="harassment",
            severity="high",
            description="test",
            reported_user_id=uuid.uuid4(),
        )
        assert result is None


class TestZeroDBClientLiveMode:
    """When credentials are set, methods call the API."""

    def setup_method(self):
        import os
        os.environ["ZERODB_API_KEY"] = "test-key"
        os.environ["ZERODB_PROJECT_ID"] = "test-project"
        os.environ["ZERODB_API_URL"] = "https://api.ainative.studio"

    def teardown_method(self):
        import os
        for k in ("ZERODB_API_KEY", "ZERODB_PROJECT_ID", "ZERODB_API_URL"):
            os.environ.pop(k, None)

    def _mock_resp(self, status_code, body):
        m = MagicMock()
        m.status_code = status_code
        m.json.return_value = body
        m.text = str(body)
        return m

    def test_store_preference_success(self):
        from app.services.zerodb_client import ZeroDBClient
        mock_resp = self._mock_resp(201, {"id": "mem_abc123"})
        with patch("httpx.post", return_value=mock_resp):
            result = ZeroDBClient().store_preference_embedding(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 10,
                metadata={"intent": "social"},
            )
        assert result == "mem_abc123"

    def test_store_preference_api_error_returns_none(self):
        from app.services.zerodb_client import ZeroDBClient
        mock_resp = self._mock_resp(500, {"error": "internal server error"})
        with patch("httpx.post", return_value=mock_resp):
            result = ZeroDBClient().store_preference_embedding(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 10,
                metadata={},
            )
        assert result is None

    def test_store_preference_network_exception_returns_none(self):
        from app.services.zerodb_client import ZeroDBClient
        with patch("httpx.post", side_effect=Exception("connection reset")):
            result = ZeroDBClient().store_preference_embedding(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 10,
                metadata={},
            )
        assert result is None

    def test_search_similar_preferences_success(self):
        from app.services.zerodb_client import ZeroDBClient
        results = [
            {"metadata": {"user_id": "user-1"}, "score": 0.92},
            {"metadata": {"user_id": "user-2"}, "score": 0.85},
        ]
        mock_resp = self._mock_resp(200, {"results": results})
        with patch("httpx.post", return_value=mock_resp):
            out = ZeroDBClient().search_similar_preferences([0.1] * 10, limit=5)
        assert len(out) == 2
        assert out[0]["score"] == 0.92

    def test_search_excludes_user_id(self):
        from app.services.zerodb_client import ZeroDBClient
        uid = uuid.uuid4()
        results = [
            {"metadata": {"user_id": str(uid)}, "score": 0.99},
            {"metadata": {"user_id": "other-user"}, "score": 0.80},
        ]
        mock_resp = self._mock_resp(200, {"results": results})
        with patch("httpx.post", return_value=mock_resp):
            out = ZeroDBClient().search_similar_preferences(
                [0.1] * 10, limit=5, exclude_user_id=uid
            )
        assert len(out) == 1
        assert out[0]["metadata"]["user_id"] == "other-user"

    def test_search_api_error_returns_empty(self):
        from app.services.zerodb_client import ZeroDBClient
        mock_resp = self._mock_resp(400, {"error": "bad request"})
        with patch("httpx.post", return_value=mock_resp):
            out = ZeroDBClient().search_similar_preferences([0.1] * 10)
        assert out == []

    def test_search_network_exception_returns_empty(self):
        from app.services.zerodb_client import ZeroDBClient
        with patch("httpx.post", side_effect=Exception("timeout")):
            out = ZeroDBClient().search_similar_preferences([0.1] * 10)
        assert out == []

    def test_enqueue_moderation_success(self):
        from app.services.zerodb_client import ZeroDBClient
        mock_resp = self._mock_resp(200, {"memory_id": "mod_xyz"})
        with patch("httpx.post", return_value=mock_resp):
            result = ZeroDBClient().enqueue_moderation_item(
                item_id=uuid.uuid4(),
                category="spam",
                severity="low",
                description="repeated spam messages",
                reported_user_id=uuid.uuid4(),
            )
        assert result == "mod_xyz"


# ── AINativeService ───────────────────────────────────────────────────────────

class TestAINativeServiceStubMode:
    """When AINATIVE_API_KEY is absent, all methods return graceful fallbacks."""

    def setup_method(self):
        import os
        os.environ.pop("AINATIVE_API_KEY", None)

    def test_generate_intro_returns_template(self):
        from app.services.ainative_service import generate_match_intro
        intro = generate_match_intro(
            requester_name="Alice",
            target_name="Bob",
            shared_interests=["hiking", "coffee"],
        )
        assert isinstance(intro, str)
        assert len(intro) > 0

    def test_embed_preferences_returns_zero_vector(self):
        from app.services.ainative_service import embed_preferences
        vec = embed_preferences(interests=["music"], personality_traits=["creative"])
        assert isinstance(vec, list)
        assert len(vec) == 768
        assert all(v == 0.0 for v in vec)

    def test_search_similar_profiles_returns_empty(self):
        from app.services.ainative_service import search_similar_profiles
        results = search_similar_profiles(embedding=[0.0] * 768)
        assert results == []

    def test_upsert_preference_vector_returns_none(self):
        from app.services.ainative_service import upsert_preference_vector
        result = upsert_preference_vector(
            user_id="user-123",
            embedding=[0.0] * 768,
            metadata={"intent": "social"},
        )
        assert result is None

    def test_moderate_message_returns_safe(self):
        from app.services.ainative_service import moderate_message
        result = moderate_message("hello there")
        assert result["safe"] is True


class TestAINativeServiceLiveMode:
    """When AINATIVE_API_KEY is set, methods call the hosted API."""

    def setup_method(self):
        import os
        os.environ["AINATIVE_API_KEY"] = "sk_test_key"
        os.environ["AINATIVE_API_URL"] = "https://api.ainative.studio"

    def teardown_method(self):
        import os
        os.environ.pop("AINATIVE_API_KEY", None)

    def _chat_resp(self, content: str):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
        return m

    def _embed_resp(self, vector: list):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"embeddings": [vector]}
        return m

    def _vector_search_resp(self, results: list):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"results": results}
        return m

    def _error_resp(self, status_code: int):
        m = MagicMock()
        m.status_code = status_code
        m.json.return_value = {"error": "api error"}
        m.text = "api error"
        return m

    def test_generate_intro_uses_llm(self):
        from app.services.ainative_service import generate_match_intro
        with patch("httpx.post", return_value=self._chat_resp("Hey! You both love hiking.")):
            intro = generate_match_intro(
                requester_name="Alice",
                target_name="Bob",
                shared_interests=["hiking"],
            )
        assert intro == "Hey! You both love hiking."

    def test_generate_intro_api_error_falls_back_to_template(self):
        from app.services.ainative_service import generate_match_intro
        with patch("httpx.post", return_value=self._error_resp(500)):
            intro = generate_match_intro(
                requester_name="Alice",
                target_name="Bob",
                shared_interests=["coffee"],
            )
        assert isinstance(intro, str)
        assert len(intro) > 0

    def test_generate_intro_exception_falls_back_to_template(self):
        from app.services.ainative_service import generate_match_intro
        with patch("httpx.post", side_effect=Exception("timeout")):
            intro = generate_match_intro(
                requester_name="Alice",
                target_name="Bob",
                shared_interests=[],
            )
        assert isinstance(intro, str)

    def test_embed_preferences_returns_768_vector(self):
        from app.services.ainative_service import embed_preferences
        vec = [0.1] * 768
        with patch("httpx.post", return_value=self._embed_resp(vec)):
            result = embed_preferences(interests=["music"], personality_traits=["creative"])
        assert len(result) == 768
        assert result[0] == pytest.approx(0.1)

    def test_embed_preferences_api_error_returns_zero_vector(self):
        from app.services.ainative_service import embed_preferences
        with patch("httpx.post", return_value=self._error_resp(503)):
            result = embed_preferences(interests=["music"], personality_traits=[])
        assert len(result) == 768
        assert all(v == 0.0 for v in result)

    def test_search_similar_profiles_returns_results(self):
        from app.services.ainative_service import search_similar_profiles
        hits = [{"id": "u1", "score": 0.9}, {"id": "u2", "score": 0.8}]
        with patch("httpx.post", return_value=self._vector_search_resp(hits)):
            results = search_similar_profiles(embedding=[0.1] * 768)
        assert len(results) == 2
        assert results[0]["id"] == "u1"

    def test_search_similar_profiles_api_error_returns_empty(self):
        from app.services.ainative_service import search_similar_profiles
        with patch("httpx.post", return_value=self._error_resp(500)):
            results = search_similar_profiles(embedding=[0.1] * 768)
        assert results == []

    def test_upsert_preference_vector_success(self):
        from app.services.ainative_service import upsert_preference_vector
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"ids": ["monadmate-pref-user-123"]}
        with patch("httpx.post", return_value=m):
            result = upsert_preference_vector(
                user_id="user-123",
                embedding=[0.1] * 768,
                metadata={"intent": "dating"},
            )
        assert result == "monadmate-pref-user-123"

    def test_moderate_message_safe(self):
        from app.services.ainative_service import moderate_message
        with patch("httpx.post", return_value=self._chat_resp('{"safe": true, "score": 0.1, "reason": "clean"}')):
            result = moderate_message("Hi there!")
        assert result["safe"] is True

    def test_moderate_message_unsafe(self):
        from app.services.ainative_service import moderate_message
        with patch("httpx.post", return_value=self._chat_resp('{"safe": false, "score": 0.95, "reason": "harassment"}')):
            result = moderate_message("threatening content")
        assert result["safe"] is False
        assert result["score"] == pytest.approx(0.95)

    def test_moderate_message_api_error_defaults_safe(self):
        from app.services.ainative_service import moderate_message
        with patch("httpx.post", return_value=self._error_resp(500)):
            result = moderate_message("some text")
        assert result["safe"] is True

    def test_moderate_message_malformed_json_defaults_safe(self):
        from app.services.ainative_service import moderate_message
        with patch("httpx.post", return_value=self._chat_resp("not valid json")):
            result = moderate_message("some text")
        assert result["safe"] is True
