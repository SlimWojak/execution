"""River resubscribe tracker — backoff for live stream recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

RESUBSCRIBE_BACKOFF_S: tuple[float, ...] = (60.0, 120.0, 300.0, 300.0, 300.0)
CONSECUTIVE_GOOD_BARS_RESET = 5
RESUBSCRIBE_MAX_ATTEMPTS = 5


class ResubscribeState(str, Enum):
    IDLE = "IDLE"
    BACKING_OFF = "BACKING_OFF"
    EXHAUSTED = "EXHAUSTED"


@dataclass
class RiverResubscribeConfig:
    backoff_delays: tuple[float, ...] = RESUBSCRIBE_BACKOFF_S
    max_attempts: int = RESUBSCRIBE_MAX_ATTEMPTS

    def get_delay(self, attempt: int) -> float:
        idx = min(attempt, len(self.backoff_delays) - 1)
        return self.backoff_delays[idx]


@dataclass
class RiverResubscribeTracker:
    """Mirror of broker ReconnectTracker with River-tuned backoff."""

    config: RiverResubscribeConfig = field(default_factory=RiverResubscribeConfig)
    state: ResubscribeState = ResubscribeState.IDLE
    attempts: int = 0
    consecutive_good_bars: int = 0
    escalated: bool = False

    def register_attempt(self) -> tuple[bool, float]:
        """Return (should_continue, delay_sec). False → escalate."""
        self.attempts += 1
        if self.attempts > self.config.max_attempts:
            self.escalated = True
            self.state = ResubscribeState.EXHAUSTED
            return (False, 0.0)
        self.state = ResubscribeState.BACKING_OFF
        return (True, self.config.get_delay(self.attempts - 1))

    def record_good_bar(self) -> None:
        self.consecutive_good_bars += 1
        if self.consecutive_good_bars >= CONSECUTIVE_GOOD_BARS_RESET and self.attempts > 0:
            self.reset()

    def record_gap(self) -> None:
        self.consecutive_good_bars = 0

    def reset(self) -> None:
        self.attempts = 0
        self.consecutive_good_bars = 0
        self.escalated = False
        self.state = ResubscribeState.IDLE

    def is_exhausted(self) -> bool:
        return self.escalated
