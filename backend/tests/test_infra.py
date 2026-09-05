"""Infrastructure tests — TTLNonceStore, health endpoint.

Covers:
- test_nonce_store_expires_after_ttl
- test_nonce_store_thread_safe
- test_health_endpoint
"""
import threading
import time
from datetime import datetime, timedelta

import pytest

from app.services.user_identity_service import TTLNonceStore


# ---------------------------------------------------------------------------
# TTLNonceStore tests
# ---------------------------------------------------------------------------


class TestTTLNonceStore:
    def test_set_and_get_returns_entry(self):
        store = TTLNonceStore(ttl_seconds=60)
        store.set("wallet_A", "nonce_abc")
        entry = store.get("wallet_A")
        assert entry is not None
        assert entry["nonce"] == "nonce_abc"

    def test_nonce_store_expires_after_ttl(self):
        """An entry stored with a 1-second TTL must not be retrievable after expiry."""
        store = TTLNonceStore(ttl_seconds=1)
        store.set("wallet_expire", "nonce_xyz")

        # Should be present immediately
        assert store.get("wallet_expire") is not None

        # Manually back-date the expiry to simulate elapsed time
        with store._lock:
            store._store["wallet_expire"]["expires_at"] = datetime.utcnow() - timedelta(seconds=1)

        # Must be gone now
        assert store.get("wallet_expire") is None

    def test_get_missing_key_returns_none(self):
        store = TTLNonceStore(ttl_seconds=60)
        assert store.get("nonexistent_key") is None

    def test_pop_removes_entry(self):
        store = TTLNonceStore(ttl_seconds=60)
        store.set("wallet_pop", "nonce_pop")
        store.pop("wallet_pop")
        assert store.get("wallet_pop") is None

    def test_pop_missing_key_is_noop(self):
        store = TTLNonceStore(ttl_seconds=60)
        # Should not raise
        store.pop("does_not_exist")

    def test_purge_expired_clears_stale_entries(self):
        store = TTLNonceStore(ttl_seconds=60)
        store.set("wallet_1", "n1")
        store.set("wallet_2", "n2")

        # Back-date wallet_1 only
        with store._lock:
            store._store["wallet_1"]["expires_at"] = datetime.utcnow() - timedelta(seconds=1)

        store.purge_expired()

        assert store.get("wallet_1") is None
        assert store.get("wallet_2") is not None

    def test_set_returns_expiry_timestamp(self):
        store = TTLNonceStore(ttl_seconds=300)
        before = datetime.utcnow()
        expires_at = store.set("wallet_ts", "nonce_ts")
        after = datetime.utcnow()

        assert before < expires_at <= after + timedelta(seconds=300)

    def test_proactive_purge_on_set(self):
        """Writing a new entry must evict expired entries in the same pass."""
        store = TTLNonceStore(ttl_seconds=60)
        store.set("wallet_old", "nonce_old")

        # Expire it manually
        with store._lock:
            store._store["wallet_old"]["expires_at"] = datetime.utcnow() - timedelta(seconds=1)

        # Writing a new entry triggers proactive purge
        store.set("wallet_new", "nonce_new")

        # Old entry should have been evicted by the proactive purge inside set()
        with store._lock:
            assert "wallet_old" not in store._store

    def test_nonce_store_thread_safe(self):
        """Concurrent writers and readers must not raise or corrupt data."""
        store = TTLNonceStore(ttl_seconds=60)
        errors: list[Exception] = []

        def writer(wallet_id: str) -> None:
            try:
                for i in range(50):
                    store.set(f"{wallet_id}_{i}", f"nonce_{wallet_id}_{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def reader(wallet_id: str) -> None:
            try:
                for i in range(50):
                    store.get(f"{wallet_id}_{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = []
        for idx in range(10):
            threads.append(threading.Thread(target=writer, args=(f"w{idx}",)))
            threads.append(threading.Thread(target=reader, args=(f"w{idx}",)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"

    def test_expired_entry_removed_from_store_on_get(self):
        """get() must physically delete the expired entry so the dict doesn't grow."""
        store = TTLNonceStore(ttl_seconds=60)
        store.set("wallet_gc", "nonce_gc")

        with store._lock:
            store._store["wallet_gc"]["expires_at"] = datetime.utcnow() - timedelta(seconds=1)

        store.get("wallet_gc")  # triggers lazy eviction

        with store._lock:
            assert "wallet_gc" not in store._store


# ---------------------------------------------------------------------------
# Health endpoint test
# ---------------------------------------------------------------------------


def test_health_endpoint(client):
    """GET /health must return 200 with status=ok and the service name."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "Monad Mate" in data["service"]
    assert "version" in data
