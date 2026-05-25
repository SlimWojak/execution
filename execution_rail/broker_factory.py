"""
Sole broker construction site.

INVARIANT: INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE
"""

from __future__ import annotations

from .broker_adapter import PaperBroker
from .broker_protocol import BrokerAdapter
from .halt_types import HaltChecker
from .mode import OperatingMode


def build_broker(
    mode: OperatingMode,
    halt: HaltChecker,
    supervisor: object | None = None,
) -> BrokerAdapter:
    if mode in (OperatingMode.TEST, OperatingMode.SHADOW):
        return PaperBroker(halt)
    if mode == OperatingMode.PAPER:
        from execution_rail.ib.config import IBKRConfig
        from execution_rail.ib.paper_adapter import IBPaperAdapter

        return IBPaperAdapter(
            halt_signal=halt,
            config=IBKRConfig.from_env(),
            supervisor=supervisor,
        )
    if mode == OperatingMode.LIVE:
        raise NotImplementedError(
            "LIVE broker not yet implemented; "
            "see MODULE.IB_LIVE_ADAPTER brief"
        )
    raise ValueError(f"unknown mode: {mode}")
