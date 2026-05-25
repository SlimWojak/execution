"""RiverSupervisor tests (TR09-TR10)."""

import time
from datetime import UTC, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from execution_rail.halt_types import LocalHaltSignal
from execution_rail.river.supervisor import RiverSupervisor

NY = ZoneInfo("America/New_York")


def test_tr09_weekend_no_halt_off_hours_alert():
    halt = LocalHaltSignal()
    alerts: list[tuple[str, str]] = []

    supervisor = RiverSupervisor(
        halt_signal=halt,
        heartbeat_interval=0.05,
        miss_threshold=2,
        check_interval=0.05,
        market_hours_only=True,
        on_alert=lambda k, d: alerts.append((k, d)),
    )
    # Saturday noon NY — market closed
    saturday_ny = datetime(2026, 5, 23, 12, 0, tzinfo=NY)

    with patch("execution_rail.river.supervisor.is_forex_market_open", return_value=False):
        supervisor.start()
        supervisor.heartbeat.beat()
        time.sleep(0.25)
        supervisor.stop()

    assert not halt.is_halted
    assert any(a[0] == "RIVER_QUIET_OFF_HOURS" for a in alerts)


def test_tr10_market_hours_escalates_halt():
    halt = LocalHaltSignal()
    supervisor = RiverSupervisor(
        halt_signal=halt,
        heartbeat_interval=0.05,
        miss_threshold=2,
        check_interval=0.05,
        market_hours_only=True,
    )

    with patch("execution_rail.river.supervisor.is_forex_market_open", return_value=True):
        supervisor.start()
        supervisor.heartbeat.beat()
        time.sleep(0.3)
        supervisor.stop()

    assert halt.is_halted
    assert halt.last_source == "ib_supervisor"
