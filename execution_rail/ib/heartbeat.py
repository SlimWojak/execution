"""Heartbeat monitor — INV-IBKR-FLAKEY-1."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HeartbeatState(str, Enum):
    ALIVE = "ALIVE"
    DEGRADED = "DEGRADED"
    DEAD = "DEAD"


@dataclass
class HeartbeatMonitor:
    interval: float = 5.0
    miss_threshold: int = 3
    on_degraded: Callable[[], None] | None = None
    on_dead: Callable[[], None] | None = None
    on_recovery: Callable[[], None] | None = None

    _last_beat_time: float | None = field(default=None, repr=False)
    _state: HeartbeatState = field(default=HeartbeatState.DEAD, repr=False)
    _beat_count: int = field(default=0, repr=False)
    _miss_count: int = field(default=0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def beat(self) -> None:
        now = time.monotonic()
        with self._lock:
            was_not_alive = self._state != HeartbeatState.ALIVE
            self._last_beat_time = now
            self._beat_count += 1
            self._miss_count = 0
            self._state = HeartbeatState.ALIVE
            if was_not_alive and self.on_recovery:
                self._lock.release()
                try:
                    self.on_recovery()
                finally:
                    self._lock.acquire()

    def check(self) -> HeartbeatState:
        now = time.monotonic()
        with self._lock:
            if self._last_beat_time is None:
                return HeartbeatState.DEAD

            missed = int((now - self._last_beat_time) / self.interval)
            old_state = self._state

            if missed >= self.miss_threshold:
                self._state = HeartbeatState.DEAD
                self._miss_count = missed
            elif missed >= 1:
                self._state = HeartbeatState.DEGRADED
                self._miss_count = missed
            else:
                self._state = HeartbeatState.ALIVE
                self._miss_count = 0

            if old_state != self._state:
                self._trigger_callback(old_state, self._state)
            return self._state

    def _trigger_callback(self, old: HeartbeatState, new: HeartbeatState) -> None:
        callback = None
        if new == HeartbeatState.DEAD and self.on_dead:
            callback = self.on_dead
        elif new == HeartbeatState.DEGRADED and self.on_degraded:
            callback = self.on_degraded
        elif new == HeartbeatState.ALIVE and old != HeartbeatState.ALIVE and self.on_recovery:
            callback = self.on_recovery
        if callback:
            self._lock.release()
            try:
                callback()
            finally:
                self._lock.acquire()

    @property
    def is_alive(self) -> bool:
        return self.check() == HeartbeatState.ALIVE

    @property
    def state(self) -> HeartbeatState:
        return self.check()

    @property
    def last_beat_age(self) -> float | None:
        with self._lock:
            if self._last_beat_time is None:
                return None
            return time.monotonic() - self._last_beat_time

    @property
    def missed_beats(self) -> int:
        self.check()
        with self._lock:
            return self._miss_count

    def reset(self) -> None:
        with self._lock:
            self._last_beat_time = None
            self._state = HeartbeatState.DEAD
            self._beat_count = 0
            self._miss_count = 0

    def get_status(self) -> dict[str, Any]:
        self.check()
        with self._lock:
            return {
                "state": self._state.value,
                "last_beat_age": self.last_beat_age,
                "beat_count": self._beat_count,
                "missed_beats": self._miss_count,
                "interval": self.interval,
                "miss_threshold": self.miss_threshold,
            }
