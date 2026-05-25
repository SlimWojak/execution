"""
Sole broker construction site.

INVARIANT: INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE

Today: PaperBroker for TEST/SHADOW/PAPER.
Future: IBPaperAdapter / IBLiveAdapter (Brief 2+).
"""

from __future__ import annotations

from .broker_adapter import PaperBroker
from .broker_protocol import BrokerAdapter
from .halt_types import HaltChecker
from .mode import OperatingMode


def build_broker(mode: OperatingMode, halt: HaltChecker) -> BrokerAdapter:
    """
    Sole broker construction site. Today: always PaperBroker.
    Future: PAPER/LIVE modes dispatch to IBPaperAdapter /
    IBLiveAdapter once those land.
    """
    if mode in (OperatingMode.TEST, OperatingMode.SHADOW, OperatingMode.PAPER):
        return PaperBroker(halt)
    if mode == OperatingMode.LIVE:
        raise NotImplementedError(
            "LIVE broker not yet implemented; "
            "see MODULE.IB_LIVE_ADAPTER brief"
        )
    raise ValueError(f"unknown mode: {mode}")
