import math
import secrets
import time
from typing import Dict, Tuple

_ble_tokens: Dict[str, float] = {}   # token -> expiry epoch
_qr_tokens: Dict[str, float] = {}    # token -> expiry epoch

BLE_TTL_SECONDS = 120   # 2 minutes
QR_TTL_SECONDS = 300    # 5 minutes


class ProximityVerificationService:
    """Handles GPS, BLE, and QR-code proximity verification for meetup attestations."""

    # ------------------------------------------------------------------ GPS
    def verify_gps(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        max_meters: float = 100.0,
    ) -> bool:
        """Return True if the two coordinates are within *max_meters* of each other."""
        dist_km = self._haversine(lat1, lon1, lat2, lon2)
        return dist_km * 1000 <= max_meters

    # ------------------------------------------------------------------ BLE
    def generate_ble_token(self) -> str:
        """Generate an 8-character hex BLE token with a 2-minute TTL."""
        token = secrets.token_hex(4)  # 4 bytes → 8 hex chars
        _ble_tokens[token] = time.time() + BLE_TTL_SECONDS
        return token

    def verify_ble_token(self, token: str, submitted: str) -> bool:
        """Verify a submitted BLE token against the stored token."""
        expiry = _ble_tokens.get(token)
        if expiry is None:
            return False
        if time.time() > expiry:
            _ble_tokens.pop(token, None)
            return False
        return token == submitted

    # ------------------------------------------------------------------ QR
    def generate_qr_token(self) -> str:
        """Generate a 16-character hex QR token with a 5-minute TTL."""
        token = secrets.token_hex(8)  # 8 bytes → 16 hex chars
        _qr_tokens[token] = time.time() + QR_TTL_SECONDS
        return token

    def verify_qr_token(self, token: str, submitted: str) -> bool:
        """Verify a submitted QR token against the stored token."""
        expiry = _qr_tokens.get(token)
        if expiry is None:
            return False
        if time.time() > expiry:
            _qr_tokens.pop(token, None)
            return False
        return token == submitted

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return great-circle distance in kilometres."""
        if any(v is None for v in (lat1, lon1, lat2, lon2)):
            return 9999.0
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))
