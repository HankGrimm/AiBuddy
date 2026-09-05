"""
ZeroDB Client — Monad Mate

Thin client for ZeroDB vector memory API (ainative.studio).
Used for:
  - Preference embedding storage (AI match agent)
  - Moderation queue persistence
  - Semantic search over user preferences

Falls back to no-op when ZERODB_API_KEY is not configured.

Refs #9
"""
import logging
import os
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("ZERODB_API_URL", "https://api.ainative.studio")


def _api_key() -> Optional[str]:
    return os.getenv("ZERODB_API_KEY")


def _project_id() -> Optional[str]:
    return os.getenv("ZERODB_PROJECT_ID")


def _is_configured() -> bool:
    return bool(_api_key() and _project_id())


class ZeroDBClient:
    """
    ZeroDB vector memory client for Monad Mate.

    All methods are best-effort — errors are logged but never raised,
    so the caller's flow is never blocked by memory infrastructure.
    """

    def store_preference_embedding(
        self,
        user_id: UUID,
        embedding: list[float],
        metadata: dict,
    ) -> Optional[str]:
        """Store a preference embedding vector in ZeroDB."""
        if not _is_configured():
            logger.debug("ZeroDB not configured — skipping preference embedding for %s", user_id)
            return None

        return self._upsert_memory(
            key=f"preference:{user_id}",
            content=metadata,
            embedding=embedding,
            tags=["preference", "monad-mate"],
        )

    def search_similar_preferences(
        self,
        embedding: list[float],
        limit: int = 10,
        exclude_user_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Semantic search for users with similar preference embeddings."""
        if not _is_configured():
            return []

        try:
            import httpx
            resp = httpx.post(
                f"{_BASE_URL}/api/v1/public/memory/v2/recall",
                json={
                    "query_embedding": embedding,
                    "limit": limit,
                    "project_id": _project_id(),
                    "tags": ["preference", "monad-mate"],
                },
                headers={"Authorization": f"Bearer {_api_key()}"},
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if exclude_user_id:
                    results = [
                        r for r in results
                        if r.get("metadata", {}).get("user_id") != str(exclude_user_id)
                    ]
                return results
        except Exception as exc:
            logger.warning("ZeroDB semantic search error: %s", exc)
        return []

    def enqueue_moderation_item(
        self,
        item_id: UUID,
        category: str,
        severity: str,
        description: str,
        reported_user_id: UUID,
    ) -> Optional[str]:
        """Persist a moderation queue item to ZeroDB for durable storage."""
        if not _is_configured():
            return None

        return self._upsert_memory(
            key=f"modqueue:{item_id}",
            content={
                "item_id": str(item_id),
                "category": category,
                "severity": severity,
                "description": description,
                "reported_user_id": str(reported_user_id),
            },
            tags=["moderation", "monad-mate", severity.lower()],
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _upsert_memory(
        self,
        key: str,
        content: Any,
        embedding: Optional[list[float]] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[str]:
        try:
            import httpx
            payload: dict = {
                "key": key,
                "content": content,
                "project_id": _project_id(),
                "tags": tags or [],
            }
            if embedding:
                payload["embedding"] = embedding

            resp = httpx.post(
                f"{_BASE_URL}/api/v1/public/memory/v2/remember",
                json=payload,
                headers={"Authorization": f"Bearer {_api_key()}"},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                memory_id = resp.json().get("id") or resp.json().get("memory_id")
                logger.debug("ZeroDB stored %s → %s", key, memory_id)
                return memory_id
            else:
                logger.warning("ZeroDB store failed HTTP %s: %s", resp.status_code, resp.text[:100])
        except Exception as exc:
            logger.warning("ZeroDB store error: %s", exc)
        return None
