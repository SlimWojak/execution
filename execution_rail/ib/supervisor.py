"""IBKR supervisor — in-session liveness, escalates to halt.signal_local."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from execution_rail.halt_types import HaltSignaler

from .heartbeat import HeartbeatMonitor, HeartbeatState


class SupervisorState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    ALERTING = "ALERTING"


@dataclass
class IBKRSupervisor:
    """
    Shadow supervisor in separate thread. Heartbeat DEAD → halt escalation.
    INV-IBKR-FLAKEY-2, INV-SUPERVISOR-1
    """

    halt_signal: HaltSignaler
    heartbeat_interval: float = 5.0
    miss_threshold: int = 3
    check_interval: float = 1.0
    on_alert: Callable[[str, str], None] | None = None
    on_recovery: Callable[[], None] | None = None
    heartbeat: HeartbeatMonitor | None = None

    _state: SupervisorState = field(default=SupervisorState.STOPPED, repr=False)
    _running: bool = field(default=False, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _halt_escalated: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if self.heartbeat is None:
            self.heartbeat = HeartbeatMonitor(
                interval=self.heartbeat_interval,
                miss_threshold=self.miss_threshold,
            )

    @property
    def state(self) -> SupervisorState:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._state = SupervisorState.RUNNING
            self._halt_escalated = False
            self._thread = threading.Thread(
                target=self._supervisor_loop,
                name="IBKRSupervisor",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        with self._lock:
            self._state = SupervisorState.STOPPED

    def _supervisor_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                self._check_heartbeat()
            except Exception as exc:
                if self.on_alert:
                    try:
                        self.on_alert("SUPERVISOR_ERROR", str(exc))
                    except Exception:
                        pass
            time.sleep(self.check_interval)

    def _check_heartbeat(self) -> None:
        if self.heartbeat is None:
            return
        hb_state = self.heartbeat.check()
        with self._lock:
            current = self._state
        if hb_state == HeartbeatState.DEAD and current != SupervisorState.ALERTING:
            self._escalate_halt("IBKR_HEARTBEAT_DEAD")
        elif hb_state == HeartbeatState.ALIVE and current == SupervisorState.ALERTING:
            self._note_recovery()

    def escalate_halt(self, reason: str) -> None:
        """Public fast path for explicit IB disconnect signals."""
        self._escalate_halt(reason)

    def _escalate_halt(self, reason: str) -> None:
        with self._lock:
            self._state = SupervisorState.ALERTING
            if self._halt_escalated:
                return
            self._halt_escalated = True
        miss = self.heartbeat.missed_beats if self.heartbeat else 0
        age = self.heartbeat.last_beat_age if self.heartbeat else None
        detail = f"miss_count={miss}, last_beat_age={age}s"
        if self.on_alert:
            try:
                self.on_alert(reason, detail)
            except Exception:
                pass
        halt_reason = "heartbeat_dead" if reason == "IBKR_HEARTBEAT_DEAD" else reason.lower()
        self.halt_signal.signal_local("ib_supervisor", halt_reason)

    def _note_recovery(self) -> None:
        with self._lock:
            self._state = SupervisorState.RUNNING
        if self.on_recovery:
            try:
                self.on_recovery()
            except Exception:
                pass

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state.value,
                "running": self._running,
                "halt_escalated": self._halt_escalated,
                "heartbeat": self.heartbeat.get_status() if self.heartbeat else {},
            }


class SupervisorWatchdog:
    """INV-SUPERVISOR-1 — alerts if supervisor thread dies."""

    def __init__(
        self,
        supervisor: IBKRSupervisor,
        check_interval: float = 10.0,
        on_supervisor_dead: Callable[[], None] | None = None,
    ) -> None:
        self.supervisor = supervisor
        self.check_interval = check_interval
        self.on_supervisor_dead = on_supervisor_dead
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="SupervisorWatchdog",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _watch_loop(self) -> None:
        while self._running:
            if not self.supervisor.is_running:
                if self.on_supervisor_dead:
                    self.on_supervisor_dead()
                break
            time.sleep(self.check_interval)


def create_ibkr_supervisor(
    halt_signal: HaltSignaler,
    on_alert: Callable[[str, str], None] | None = None,
    on_recovery: Callable[[], None] | None = None,
) -> tuple[IBKRSupervisor, SupervisorWatchdog]:
    supervisor = IBKRSupervisor(
        halt_signal=halt_signal,
        on_alert=on_alert,
        on_recovery=on_recovery,
    )

    def on_supervisor_dead() -> None:
        if on_alert:
            on_alert("SUPERVISOR_DEAD", "IBKRSupervisor stopped unexpectedly")

    watchdog = SupervisorWatchdog(supervisor, on_supervisor_dead=on_supervisor_dead)
    return supervisor, watchdog
