from uuid import UUID
from datetime import datetime
import uuid
from typing import Optional


# In-memory store for hackathon; ZeroDB used for durable persistence when configured.
_queue: list[dict] = []


class ModerationQueueService:
    """Moderation queue — in-memory for hackathon, ZeroDB-backed in prod."""

    def enqueue(
        self,
        report_id: UUID,
        severity: str,
        auto_action: Optional[str] = None,
        reported_user_id: Optional[UUID] = None,
        category: str = "unknown",
        description: str = "",
    ) -> dict:
        item = {
            "id": str(uuid.uuid4()),
            "report_id": str(report_id),
            "severity": severity,
            "auto_action": auto_action,
            "status": "pending",
            "reviewer_id": None,
            "review_notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
        }
        _queue.append(item)

        # Best-effort durable persistence via ZeroDB
        if reported_user_id:
            try:
                from .zerodb_client import ZeroDBClient
                ZeroDBClient().enqueue_moderation_item(
                    item_id=uuid.UUID(item["id"]),
                    category=category,
                    severity=severity,
                    description=description,
                    reported_user_id=reported_user_id,
                )
            except Exception:
                pass  # Never block on ZeroDB

        return item

    def get_pending(self, limit: int = 20) -> list[dict]:
        pending = [item for item in _queue if item["status"] == "pending"]
        return pending[:limit]

    def resolve_item(self, item_id: str, reviewer_id: UUID, notes: str) -> dict:
        for item in _queue:
            if item["id"] == item_id:
                item["status"] = "resolved"
                item["reviewer_id"] = str(reviewer_id)
                item["review_notes"] = notes
                item["resolved_at"] = datetime.utcnow().isoformat()
                return item
        raise KeyError(f"Moderation item {item_id} not found")

    @staticmethod
    def clear() -> None:
        """Test helper — wipes the in-memory queue."""
        _queue.clear()
