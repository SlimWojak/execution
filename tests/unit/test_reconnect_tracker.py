"""ReconnectTracker tests (TS13-TS16)."""

from datetime import UTC, datetime, timedelta

from execution_rail.ib.config import ReconnectConfig, ReconnectState, ReconnectTracker


def test_ts13_backoff_sequence():
    tracker = ReconnectTracker(config=ReconnectConfig(backoff_delays=(1.0, 2.0, 3.0)))
    tracker.begin()
    cont, d1 = tracker.register_attempt()
    cont2, d2 = tracker.register_attempt()
    assert cont and d1 == 1.0
    assert cont2 and d2 == 2.0


def test_ts14_escalate_at_max_attempts():
    tracker = ReconnectTracker(config=ReconnectConfig(max_attempts=2, backoff_delays=(0.1, 0.2)))
    tracker.begin()
    tracker.register_attempt()
    cont, _ = tracker.register_attempt()
    assert not cont
    assert tracker.escalated


def test_ts15_time_budget_escalation():
    tracker = ReconnectTracker(config=ReconnectConfig(max_attempts=99, max_time_sec=0.0))
    tracker.begin()
    tracker.started_at = datetime.now(UTC) - timedelta(seconds=1)
    cont, _ = tracker.register_attempt()
    assert not cont
    assert tracker.state == ReconnectState.ESCALATED


def test_ts16_reset_on_success():
    tracker = ReconnectTracker()
    tracker.begin()
    tracker.register_attempt()
    tracker.record_success()
    assert tracker.attempts == 0
    assert tracker.state == ReconnectState.CONNECTED
