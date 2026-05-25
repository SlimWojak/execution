"""Supervisor + watchdog tests (TS08-TS12)."""

import time

from execution_rail.halt_types import LocalHaltSignal
from execution_rail.ib.heartbeat import HeartbeatState
from execution_rail.ib.supervisor import (
    IBKRSupervisor,
    SupervisorState,
    SupervisorWatchdog,
    create_ibkr_supervisor,
)


def test_ts08_start_stop_clean():
    halt = LocalHaltSignal()
    supervisor, watchdog = create_ibkr_supervisor(halt)
    supervisor.start()
    watchdog.start()
    time.sleep(0.2)
    supervisor.stop()
    watchdog.stop()
    assert supervisor.state == SupervisorState.STOPPED


def test_ts09_heartbeat_dead_escalates_halt_once():
    halt = LocalHaltSignal()
    supervisor = IBKRSupervisor(
        halt_signal=halt,
        heartbeat_interval=0.05,
        miss_threshold=2,
        check_interval=0.05,
    )
    supervisor.start()
    supervisor.heartbeat.beat()
    time.sleep(0.25)
    time.sleep(0.15)
    supervisor.stop()
    assert halt.is_halted
    assert halt.last_source == "ib_supervisor"


def test_ts10_recovery_does_not_clear_halt():
    halt = LocalHaltSignal()
    supervisor = IBKRSupervisor(
        halt_signal=halt,
        heartbeat_interval=0.05,
        miss_threshold=2,
        check_interval=0.05,
    )
    supervisor.start()
    supervisor.heartbeat.beat()
    time.sleep(0.3)
    supervisor.heartbeat.beat()
    time.sleep(0.1)
    supervisor.stop()
    assert halt.is_halted
    assert supervisor.state in (SupervisorState.RUNNING, SupervisorState.STOPPED)


def test_ts11_on_alert_raise_survives_loop():
    halt = LocalHaltSignal()
    calls = {"n": 0}

    def bad_alert(_kind: str, _msg: str) -> None:
        calls["n"] += 1
        raise RuntimeError("alert failed")

    supervisor = IBKRSupervisor(
        halt_signal=halt,
        on_alert=bad_alert,
        heartbeat_interval=0.05,
        miss_threshold=2,
        check_interval=0.05,
    )
    supervisor.start()
    supervisor.heartbeat.beat()
    time.sleep(0.35)
    supervisor.stop()
    assert calls["n"] >= 1
    assert halt.is_halted


def test_ts12_watchdog_fires_on_supervisor_death():
    halt = LocalHaltSignal()
    fired = {"dead": False}

    supervisor = IBKRSupervisor(halt_signal=halt, check_interval=0.05)
    watchdog = SupervisorWatchdog(
        supervisor,
        check_interval=0.05,
        on_supervisor_dead=lambda: fired.update(dead=True),
    )
    supervisor.start()
    watchdog.start()
    supervisor.stop()
    time.sleep(0.2)
    watchdog.stop()
    assert fired["dead"]
