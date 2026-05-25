"""River resubscribe tracker tests (TR07-TR08)."""

from execution_rail.river.resubscribe import (
    CONSECUTIVE_GOOD_BARS_RESET,
    RESUBSCRIBE_BACKOFF_S,
    RiverResubscribeTracker,
)


def test_tr07_backoff_sequence_then_escalate():
    tracker = RiverResubscribeTracker()
    delays = []
    for _ in range(len(RESUBSCRIBE_BACKOFF_S)):
        cont, delay = tracker.register_attempt()
        assert cont
        delays.append(delay)
    assert delays == list(RESUBSCRIBE_BACKOFF_S)
    cont, _ = tracker.register_attempt()
    assert not cont
    assert tracker.is_exhausted()


def test_tr08_reset_after_consecutive_good_bars():
    tracker = RiverResubscribeTracker()
    tracker.register_attempt()
    tracker.register_attempt()
    assert tracker.attempts == 2
    for _ in range(CONSECUTIVE_GOOD_BARS_RESET):
        tracker.record_good_bar()
    assert tracker.attempts == 0
    assert not tracker.is_exhausted()
