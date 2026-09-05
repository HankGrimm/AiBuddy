from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import uuid
import threading
from typing import Optional

from ..models.user import User
from ..schemas.user import UserOnboard, UserResponse, UserUpdate, WalletAuthChallenge, WalletAuthToken
from ..core.auth import create_access_token
from ..core.errors import UserNotFoundError


class TTLNonceStore:
    """Thread-safe in-memory nonce store with TTL expiry.

    Entries are evicted lazily (on read) and proactively (on write) so the
    dict never grows unbounded.  All public methods acquire ``_lock`` for
    safe concurrent access.

    In production, replace with a Redis-backed store.

    Args:
        ttl_seconds: Lifetime of each nonce in seconds (default 300 = 5 min).
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._store: dict = {}
        self._lock = threading.Lock()

    def set(self, key: str, nonce: str, expires_at: Optional[datetime] = None) -> datetime:
        """Store *nonce* for *key* and return its expiry timestamp."""
        if expires_at is None:
            expires_at = datetime.utcnow() + self._ttl
        with self._lock:
            self._purge_expired_locked()
            self._store[key] = {"nonce": nonce, "expires_at": expires_at}
        return expires_at

    def get(self, key: str) -> Optional[dict]:
        """Return the entry for *key*, or ``None`` if absent / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry["expires_at"] < datetime.utcnow():
                del self._store[key]
                return None
            return dict(entry)

    def pop(self, key: str) -> None:
        """Remove the entry for *key* (no-op if absent)."""
        with self._lock:
            self._store.pop(key, None)

    def purge_expired(self) -> None:
        """Remove all expired entries (public helper for maintenance)."""
        with self._lock:
            self._purge_expired_locked()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _purge_expired_locked(self) -> None:
        """Evict expired entries.  Caller MUST hold ``_lock``."""
        now = datetime.utcnow()
        expired = [k for k, v in self._store.items() if v["expires_at"] < now]
        for k in expired:
            del self._store[k]


# Module-level singleton — shared across requests in the same process
_nonce_store = TTLNonceStore(ttl_seconds=300)


def _verify_monad_signature(wallet_address: str, nonce: str, signature: str) -> bool:
    """Verify that `signature` is a valid EIP-191 personal_sign of `nonce` by `wallet_address`.

    The signature is the 65-byte (r, s, v) blob returned by
    ``personal_sign`` / ``eth_sign`` in EVM wallets (MetaMask, Rabby, ...),
    hex-encoded with or without the ``0x`` prefix.

    Returns True if valid, False otherwise.
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        sig = signature if signature.startswith("0x") else f"0x{signature}"
        if len(bytes.fromhex(sig[2:])) != 65:
            return False

        recovered = Account.recover_message(encode_defunct(text=nonce), signature=sig)
        return recovered.lower() == wallet_address.lower()
    except Exception:
        return False


class UserIdentityService:
    def __init__(self, db: Session):
        self.db = db

    def create_challenge(self, wallet_address: str) -> WalletAuthChallenge:
        nonce = secrets.token_hex(32)
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        _nonce_store.set(wallet_address, nonce, expires_at)
        return WalletAuthChallenge(nonce=nonce, expires_at=expires_at)

    def onboard(self, payload: UserOnboard) -> WalletAuthToken:
        from fastapi import HTTPException

        # Verify nonce exists and is not expired
        stored = _nonce_store.get(payload.wallet_address)
        if not stored or stored["nonce"] != payload.nonce:
            raise HTTPException(status_code=401, detail="Invalid or expired nonce")

        # Verify EIP-191 wallet signature
        if not _verify_monad_signature(
            payload.wallet_address, payload.nonce, payload.signature
        ):
            raise HTTPException(status_code=401, detail="Invalid wallet signature")

        # Consume the nonce (one-time use)
        _nonce_store.pop(payload.wallet_address)

        # Upsert user
        user = self.db.query(User).filter(User.wallet_address == payload.wallet_address).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                wallet_address=payload.wallet_address,
                email=payload.email,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        token = create_access_token(str(user.id), user.wallet_address)
        return WalletAuthToken(access_token=token, user=UserResponse.model_validate(user))

    def update_user(self, user: User, payload: UserUpdate) -> User:
        if payload.email is not None:
            user.email = payload.email
        if payload.privacy_mode is not None:
            user.privacy_mode = payload.privacy_mode
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user
