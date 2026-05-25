"""RiverSupervisor — River-tuned IBKRSupervisor with market-hours gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from execution_rail.halt_types import HaltSignaler
from execution_rail.ib.supervisor import IBKRSupervisor

from .market_hours import is_forex_market_open


@dataclass
class RiverSupervisor(IBKRSupervisor):
    """River-tuned supervisor. Gates halt escalation on forex market hours."""

    heartbeat_interval: float = 60.0
    miss_threshold: int = 3
    check_interval: float = 10.0
    market_hours_only: bool = True

    def pulse_heartbeat(self) -> None:
        if self.heartbeat is not None:
            self.heartbeat.beat()

    def _escalate_halt(self, reason: str) -> None:
        if self.market_hours_only and not is_forex_market_open():
            if self.on_alert:
                try:
                    self.on_alert(
                        "RIVER_QUIET_OFF_HOURS",
                        f"bars stale during closed market: {reason}",
                    )
                except Exception:
                    pass
            return
        super()._escalate_halt(reason)


def create_river_supervisor(
    halt_signal: HaltSignaler,
    on_alert: Callable[[str, str], None] | None = None,
    *,
    market_hours_only: bool = True,
) -> RiverSupervisor:
    return RiverSupervisor(
        halt_signal=halt_signal,
        on_alert=on_alert,
        market_hours_only=market_hours_only,
    )
