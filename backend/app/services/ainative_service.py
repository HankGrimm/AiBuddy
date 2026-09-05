"""
AINative LLM & Embedding Service — Monad Mate

Routes AI inference through AINative Studio's serverless API:
  - OpenAI-compatible chat completions for intro generation
  - ZeroDB /zerodb/embed for real 768-dim BAAI/bge embeddings
  - ZeroDB /zerodb/vectors/search for semantic similarity search

Falls back gracefully when AINATIVE_API_KEY is not set.

Base URL: https://api.ainative.studio
Auth:     X-API-Key: <AINATIVE_API_KEY>
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = os.getenv("AINATIVE_API_URL", "https://api.ainative.studio")
_EMBEDDING_DIM = 768  # BAAI/bge-base-en-v1.5


def _api_key() -> Optional[str]:
    return os.getenv("AINATIVE_API_KEY")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "X-API-Key": _api_key() or "",
        "Content-Type": "application/json",
    }


def _is_configured() -> bool:
    return bool(_api_key())


# ---------------------------------------------------------------------------
# LLM: intro generation
# ---------------------------------------------------------------------------

def generate_match_intro(
    *,
    requester_name: str,
    target_name: str,
    shared_interests: list[str],
    requester_intent: Optional[str] = None,
    context: Optional[str] = None,
) -> str:
    """
    Generate a personalised opening message via AINative LLM (llama-3.3-70b).
    Falls back to a deterministic template if the API is unavailable.
    """
    if not _is_configured():
        return _fallback_intro(requester_name, target_name, shared_interests, context)

    interest_str = ", ".join(shared_interests[:5]) if shared_interests else "similar vibes"
    intent_hint = f" (intent: {requester_intent})" if requester_intent else ""
    context_hint = f"\nExtra context from requester: {context}" if context else ""

    system = (
        "You are a warm, witty social connector. Write a short, genuine opening message "
        "from one person to another. Keep it under 60 words. Natural, no emojis, no cringe."
    )
    user_prompt = (
        f"{requester_name} wants to connect with {target_name}{intent_hint}.\n"
        f"They share interests in: {interest_str}.{context_hint}\n"
        f"Write an opening DM from {requester_name} to {target_name}."
    )

    try:
        resp = httpx.post(
            f"{_BASE}/api/v1/chat/completions",
            json={
                "model": "llama-3.3-70b",
                "max_tokens": 120,
                "temperature": 0.75,
                "messages": [{"role": "user", "content": user_prompt}],
                "system": system,
            },
            headers=_headers(),
            timeout=12,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            logger.info("AINative LLM generated intro (%d chars)", len(content))
            return content
        else:
            logger.warning("AINative LLM HTTP %s: %s", resp.status_code, resp.text[:80])
    except Exception as exc:
        logger.warning("AINative LLM error: %s", exc)

    return _fallback_intro(requester_name, target_name, shared_interests, context)


def _fallback_intro(
    requester_name: str,
    target_name: str,
    shared_interests: list[str],
    context: Optional[str],
) -> str:
    parts = [f"Hi {target_name}!"]
    if shared_interests:
        parts.append(f"We both love {', '.join(shared_interests[:3])}.")
    if context:
        parts.append(context)
    parts.append("Looks like we might vibe well together.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Embeddings: real 768-dim vectors via AINative ZeroDB
# ---------------------------------------------------------------------------

def embed_text(text: str) -> list[float]:
    """
    Generate a 768-dim BAAI/bge-base-en-v1.5 embedding via AINative /zerodb/embed.
    Returns a zero vector on failure (safe for cosine similarity — treated as no-match).
    """
    if not _is_configured():
        logger.debug("AINative not configured — returning zero embedding")
        return [0.0] * _EMBEDDING_DIM

    try:
        resp = httpx.post(
            f"{_BASE}/zerodb/embed",
            json={"texts": [text]},
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Response: {"embeddings": [[...768 floats...]]}
            embeddings = data.get("embeddings") or data.get("data", [])
            if embeddings and len(embeddings) > 0:
                vec = embeddings[0]
                if isinstance(vec, dict):
                    vec = vec.get("embedding", [])
                logger.debug("AINative embed: %d-dim vector", len(vec))
                return vec
        logger.warning("AINative embed HTTP %s: %s", resp.status_code, resp.text[:80])
    except Exception as exc:
        logger.warning("AINative embed error: %s", exc)

    return [0.0] * _EMBEDDING_DIM


def embed_preferences(interests: list[str], personality_traits: list[str]) -> list[float]:
    """
    Embed a user's preference profile as a single semantic vector.
    Joins interests + personality traits into a natural-language string.
    """
    if not interests and not personality_traits:
        return [0.0] * _EMBEDDING_DIM

    text = "Interests: " + ", ".join(interests or [])
    if personality_traits:
        text += ". Personality: " + ", ".join(personality_traits)

    return embed_text(text)


# ---------------------------------------------------------------------------
# Vector search: semantic similarity via ZeroDB
# ---------------------------------------------------------------------------

def search_similar_profiles(
    embedding: list[float],
    namespace: str = "monad-mate-preferences",
    limit: int = 20,
    min_score: float = 0.5,
) -> list[dict]:
    """
    Semantic search over stored preference embeddings using ZeroDB vector store.
    Returns list of {id, text, score, metadata} dicts.
    """
    if not _is_configured():
        return []

    # Skip search if embedding is a zero vector (unconfigured fallback)
    if all(v == 0.0 for v in embedding[:10]):
        return []

    try:
        resp = httpx.post(
            f"{_BASE}/zerodb/vectors/search",
            json={
                "query": embedding,
                "limit": limit,
                "min_score": min_score,
                "namespace": namespace,
            },
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            logger.debug("ZeroDB vector search: %d results", len(results))
            return results
        logger.warning("ZeroDB search HTTP %s: %s", resp.status_code, resp.text[:80])
    except Exception as exc:
        logger.warning("ZeroDB search error: %s", exc)

    return []


def upsert_preference_vector(
    user_id: str,
    embedding: list[float],
    metadata: dict,
    namespace: str = "monad-mate-preferences",
) -> Optional[str]:
    """
    Store or update a preference embedding in ZeroDB vector store.
    Returns the vector ID on success, None on failure.
    """
    if not _is_configured():
        return None

    if all(v == 0.0 for v in embedding[:10]):
        return None

    try:
        resp = httpx.post(
            f"{_BASE}/zerodb/vectors/upsert",
            json={
                "texts": [metadata.get("profile_text", str(user_id))],
                "ids": [f"monadmate-pref-{user_id}"],
                "metadata": [{"user_id": user_id, **metadata}],
                "namespace": namespace,
            },
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code in (200, 201):
            vector_id = resp.json().get("ids", [None])[0]
            logger.debug("ZeroDB upserted preference for user %s → %s", user_id, vector_id)
            return vector_id
        logger.warning("ZeroDB upsert HTTP %s: %s", resp.status_code, resp.text[:80])
    except Exception as exc:
        logger.warning("ZeroDB upsert error: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Content moderation: AI safety check
# ---------------------------------------------------------------------------

def moderate_message(text: str) -> dict:
    """
    Quick safety check on a message before delivery.
    Returns {"safe": bool, "reason": str, "score": float}.
    Falls back to safe=True if unconfigured.
    """
    if not _is_configured() or not text:
        return {"safe": True, "reason": "unchecked", "score": 1.0}

    try:
        resp = httpx.post(
            f"{_BASE}/api/v1/chat/completions",
            json={
                "model": "llama-3.1-8b",
                "max_tokens": 20,
                "temperature": 0.0,
                "messages": [{
                    "role": "user",
                    "content": (
                        f'Rate this message safety for a social app (respond with only JSON '
                        f'{{"safe":true/false,"score":0.0-1.0,"reason":"one word"}}):\n"{text}"'
                    )
                }],
            },
            headers=_headers(),
            timeout=8,
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            import json
            # Extract JSON from response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(raw[start:end])
                return {
                    "safe": bool(result.get("safe", True)),
                    "reason": result.get("reason", "ok"),
                    "score": float(result.get("score", 1.0)),
                }
    except Exception as exc:
        logger.warning("AINative moderation error: %s", exc)

    return {"safe": True, "reason": "unchecked", "score": 1.0}
