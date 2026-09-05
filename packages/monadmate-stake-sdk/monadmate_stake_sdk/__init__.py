"""
monadmate-stake-sdk — Stake-gated access control for Monad dApps

Any Monad dApp can require a MON stake before a DM, room entry, or action.
Extracted from Monad Mate Trust API.

Install: pip install monadmate-stake-sdk

Features:
  - Stake lifecycle: create → active → refund/slash
  - Three stake types: dm_unlock, room_entry, meetup_request
  - Monad EventLog on-chain recording
  - Per-type minimum MON amounts
  - Repeat offender multiplier (each no-show raises required stake 0.5×)
"""

from .stake import StakeType, StakeStatus, StakeRecord, StakeGate
from .slashing import SlashingPolicy, SlashReason

__version__ = "0.1.0"
__all__ = [
    "StakeType",
    "StakeStatus",
    "StakeRecord",
    "StakeGate",
    "SlashingPolicy",
    "SlashReason",
]
