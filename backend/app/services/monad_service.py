"""
MonadService — submits transactions to Monad testnet to record stake events
on-chain. Writes each stake/refund/slash into the ``MonadMateEventLog``
contract so every decision produces a real, explorer-visible transaction
without requiring the full ERC20 escrow flow to be wired up.

If no event-log address is configured, the service falls back to a zero-value
self-transaction carrying the JSON payload in calldata — still verifiable on
the explorer, no deploy required.

Graceful degradation: if the signing key is missing or any RPC call fails, the
methods return None so the rest of the API keeps working normally.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# MonadMateEventLog.write(bytes32 eventType, bytes32 refId, string payload)
EVENT_LOG_ABI = [
    {
        "type": "function",
        "name": "write",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "eventType", "type": "bytes32"},
            {"name": "refId", "type": "bytes32"},
            {"name": "payload", "type": "string"},
        ],
        "outputs": [{"name": "sequence", "type": "uint256"}],
    }
]


def _load_private_key() -> Optional[str]:
    """Return the backend signer key as a 0x-prefixed hex string.

    Reads ``MONAD_PRIVATE_KEY`` first, then falls back to the file at
    ``MONAD_KEYSTORE_PATH`` (a plain file containing the hex key).  Returns
    None when neither is available so callers can degrade gracefully.
    """
    key = os.environ.get("MONAD_PRIVATE_KEY")
    if not key:
        try:
            from ..core.config import settings  # noqa: PLC0415

            key = settings.MONAD_PRIVATE_KEY or ""
            raw_path = settings.MONAD_KEYSTORE_PATH
        except Exception:
            raw_path = os.environ.get("MONAD_KEYSTORE_PATH", "~/.monad/backend.key")

        if not key and raw_path:
            key_path = Path(raw_path).expanduser()
            if not key_path.exists():
                logger.debug(
                    "Monad signing key not found at %s — skipping on-chain record", key_path
                )
                return None
            key = key_path.read_text().strip()

    if not key:
        return None
    return key if key.startswith("0x") else f"0x{key}"


def _rpc_url() -> str:
    """Return the Monad RPC URL, preferring the config module value."""
    try:
        from ..core.config import settings  # noqa: PLC0415

        return settings.MONAD_RPC_URL
    except Exception:
        return os.environ.get("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")


def _event_log_address() -> str:
    try:
        from ..core.config import settings  # noqa: PLC0415

        return settings.MONAD_EVENT_LOG_ADDRESS or ""
    except Exception:
        return os.environ.get("MONAD_EVENT_LOG_ADDRESS", "")


def _chain_id() -> int:
    try:
        from ..core.config import settings  # noqa: PLC0415

        return settings.MONAD_CHAIN_ID
    except Exception:
        return int(os.environ.get("MONAD_CHAIN_ID", "10143"))


def _to_bytes32(value: str) -> bytes:
    """Right-pad a short UTF-8 tag to 32 bytes (truncating if oversized)."""
    return value.encode("utf-8")[:32].ljust(32, b"\x00")


class MonadService:
    """Submits lightweight record transactions to Monad testnet.

    Each public method serialises the event as JSON and writes it to the
    ``MonadMateEventLog`` contract (or as calldata on a self-transaction when
    no contract address is configured).  The sender is the key loaded from
    ``MONAD_PRIVATE_KEY`` / ``MONAD_KEYSTORE_PATH``.  All methods return the
    0x-prefixed transaction hash on success, or ``None`` on any error.
    """

    def _submit_record(self, event_type: str, ref_id: str, payload: dict) -> Optional[str]:
        """Core helper: build, sign and send a single record transaction.

        Returns the tx hash string or None.
        """
        private_key = _load_private_key()
        if private_key is None:
            return None

        try:
            from eth_account import Account  # type: ignore
            from web3 import Web3  # type: ignore

            w3 = Web3(Web3.HTTPProvider(_rpc_url()))
            account = Account.from_key(private_key)

            payload_json = json.dumps(payload, separators=(",", ":"))
            base_tx = {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": _chain_id(),
            }

            log_address = _event_log_address()
            if log_address:
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(log_address), abi=EVENT_LOG_ABI
                )
                tx = contract.functions.write(
                    _to_bytes32(event_type), _to_bytes32(ref_id), payload_json
                ).build_transaction(base_tx)
            else:
                # No event-log contract configured — record the payload as
                # calldata on a zero-value self-transfer.
                # Monad charges gas on the *limit*, not usage, and a plain
                # transfer is always exactly 21,000 — hardcode it instead
                # of paying for a padded estimate.
                tx = {
                    **base_tx,
                    "to": account.address,
                    "value": 0,
                    "gas": 21_000,
                    "data": Web3.to_hex(payload_json.encode("utf-8")),
                }

            # Only fill fee fields the builder left out — mixing legacy
            # gasPrice with EIP-1559 fields would make the tx unsignable.
            if "gasPrice" not in tx and "maxFeePerGas" not in tx:
                tx["maxFeePerGas"] = w3.eth.gas_price * 2
                tx["maxPriorityFeePerGas"] = w3.eth.max_priority_fee

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hash_hex = Web3.to_hex(tx_hash)
            logger.info(
                "Monad record tx submitted | event=%s tx=%s",
                event_type,
                tx_hash_hex,
            )
            return tx_hash_hex

        except Exception as exc:
            logger.warning(
                "Monad record tx failed (non-fatal) | event=%s error=%s",
                event_type,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_stake_record(
        self,
        stake_id: str,
        user_wallet: Optional[str],
        amount_mon: float,
        stake_type: str,
    ) -> Optional[str]:
        """Record a stake event on-chain.

        Returns the testnet tx hash or None if Monad is unavailable.
        """
        payload = {
            "event": "stake",
            "contract": _event_log_address(),
            "stake_id": str(stake_id),
            "wallet": user_wallet,
            "amount": round(amount_mon, 6),
            "type": str(stake_type),
        }
        return self._submit_record("stake", str(stake_id), payload)

    def submit_refund_record(
        self,
        stake_id: str,
        user_wallet: Optional[str],
        amount_mon: float,
    ) -> Optional[str]:
        """Record a refund event on-chain.

        Returns the testnet tx hash or None if Monad is unavailable.
        """
        payload = {
            "event": "refund",
            "contract": _event_log_address(),
            "stake_id": str(stake_id),
            "wallet": user_wallet,
            "amount": round(amount_mon, 6),
        }
        return self._submit_record("refund", str(stake_id), payload)

    def submit_slash_record(
        self,
        stake_id: str,
        user_wallet: Optional[str],
        amount_mon: float,
        reason: str,
    ) -> Optional[str]:
        """Record a slash event on-chain.

        Returns the testnet tx hash or None if Monad is unavailable.
        """
        payload = {
            "event": "slash",
            "contract": _event_log_address(),
            "stake_id": str(stake_id),
            "wallet": user_wallet,
            "amount": round(amount_mon, 6),
            "reason": reason,
        }
        return self._submit_record("slash", str(stake_id), payload)
