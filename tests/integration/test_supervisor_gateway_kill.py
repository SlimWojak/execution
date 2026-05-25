"""Env-gated supervisor integration (TS17)."""

from __future__ import annotations

import os

import pytest

from execution_rail.halt_types import HaltError, LocalHaltSignal
from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter
from execution_rail.ib.supervisor import create_ibkr_supervisor

pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.getenv("IBKR_INTEGRATION_TEST", "").strip() == "1"


@pytest.mark.skipif(not _enabled(), reason="IBKR_INTEGRATION_TEST=1 not set")
def test_ts17_gateway_kill_halts_next_open():
    halt = LocalHaltSignal()
    supervisor, watchdog = create_ibkr_supervisor(halt)
    supervisor.start()
    watchdog.start()
    config = IBKRConfig.from_env()
    if config.mode != IBKRMode.PAPER:
        pytest.skip("IBKR_MODE must be PAPER")
    adapter = IBPaperAdapter(halt, config, supervisor=supervisor)
    try:
        adapter._ensure_connected()
        adapter._client.disconnect()
        adapter._connected = False
        supervisor.heartbeat.reset()
        import time
        time.sleep(0.3)
        for _ in range(20):
            supervisor.heartbeat.check()
            time.sleep(0.05)
        assert halt.is_halted
        with pytest.raises(HaltError):
            adapter.open_position("EURUSD", "LONG", 20000.0, 0.0)
    finally:
        adapter.disconnect()
        supervisor.stop()
        watchdog.stop()
