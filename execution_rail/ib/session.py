"""Supervised PAPER session helper — Layer 2 wiring for orchestrators."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from typing import Callable, Iterator

from execution_rail.halt_types import HaltSignaler
from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter
from execution_rail.ib.supervisor import IBKRSupervisor, SupervisorWatchdog, create_ibkr_supervisor
from execution_rail.mode import OperatingMode
from execution_rail.mode_promotion import assert_mode_granted


@contextmanager
def supervised_paper_session(
    halt: HaltSignaler,
    on_alert: Callable[[str, str], None] | None = None,
    on_recovery: Callable[[], None] | None = None,
) -> Iterator[tuple[IBPaperAdapter, IBKRSupervisor, SupervisorWatchdog]]:
    """Start supervisor + watchdog, yield adapter, clean stop in finally."""
    assert_mode_granted(OperatingMode.PAPER)
    supervisor, watchdog = create_ibkr_supervisor(
        halt_signal=halt,
        on_alert=on_alert,
        on_recovery=on_recovery,
    )
    supervisor.start()
    watchdog.start()
    if on_alert:
        on_alert("SUPERVISOR_STARTED", "layer-2 active")
    config = replace(IBKRConfig.from_env(), mode=IBKRMode.PAPER)
    config._set_mode_defaults()
    adapter = IBPaperAdapter(halt, config, supervisor=supervisor)
    try:
        yield adapter, supervisor, watchdog
    finally:
        adapter.disconnect()
        supervisor.stop()
        watchdog.stop()
        if on_alert:
            on_alert("SUPERVISOR_STOPPED", "layer-2 stopped")
