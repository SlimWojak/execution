"""
Sole broker construction site.

INVARIANT: INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE
"""

from __future__ import annotations

from dataclasses import replace

from .broker_adapter import PaperBroker
from .broker_protocol import BrokerAdapter
from .halt_types import HaltChecker
from .ib.config import IBKRConfig, IBKRMode
from .ib.paper_adapter import IBPaperAdapter
from .ib.supervisor import IBKRSupervisor
from .mode import OperatingMode
from .mode_promotion import assert_mode_granted


def build_broker(
    mode: OperatingMode,
    halt: HaltChecker,
    supervisor: IBKRSupervisor | None = None,
) -> BrokerAdapter:
    if mode in (OperatingMode.TEST, OperatingMode.SHADOW):
        if supervisor is not None:
            raise ValueError("supervisor is only valid for PAPER mode")
        return PaperBroker(halt)
    if mode == OperatingMode.PAPER:
        assert_mode_granted(OperatingMode.PAPER)
        config = replace(IBKRConfig.from_env(), mode=IBKRMode.PAPER)
        config._set_mode_defaults()
        return IBPaperAdapter(
            halt_signal=halt,
            config=config,
            supervisor=supervisor,
        )
    if mode == OperatingMode.LIVE:
        raise NotImplementedError(
            "LIVE broker not yet implemented; "
            "see MODULE.IB_LIVE_ADAPTER brief"
        )
    raise ValueError(f"unknown mode: {mode}")
