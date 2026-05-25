"""Heartbeat monitor tests (TS05-TS07)."""

import threading
import time

from execution_rail.ib.heartbeat import HeartbeatMonitor, HeartbeatState


def test_ts05_beat_alive():
    monitor = HeartbeatMonitor(interval=0.1, miss_threshold=3)
    monitor.beat()
    assert monitor.state == HeartbeatState.ALIVE


def test_ts06_no_beats_dead():
    monitor = HeartbeatMonitor(interval=0.05, miss_threshold=2)
    monitor.beat()
    time.sleep(0.2)
    assert monitor.check() == HeartbeatState.DEAD


def test_ts07_recovery_callback():
    recovered = {"called": False}

    def on_recovery() -> None:
        recovered["called"] = True

    monitor = HeartbeatMonitor(interval=0.05, miss_threshold=2, on_recovery=on_recovery)
    monitor.beat()
    time.sleep(0.2)
    monitor.check()
    monitor.beat()
    assert recovered["called"]


def test_get_status_returns_without_deadlock():
    monitor = HeartbeatMonitor(interval=0.1, miss_threshold=3)
    monitor.beat()
    result = {"done": False}

    def read_status() -> None:
        monitor.get_status()
        result["done"] = True

    thread = threading.Thread(target=read_status, daemon=True)
    thread.start()
    thread.join(0.5)
    assert result["done"]
