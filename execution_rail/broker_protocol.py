"""
BrokerAdapter Protocol — sole broker contract for the execution rail.

Every broker implementation (PaperBroker, IBPaperAdapter, IBLiveAdapter)
must satisfy this Protocol. Strategy and orchestrator code depend on the
Protocol type, never a concrete class.

INVARIANT: INV-BROKER-PROTOCOL-IS-CONTRACT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class OrderIntent:
    """Candidate_C intent cargo handed to the execution rail."""

    symbol: str
    direction: str
    size: float
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class FillEvent:
    success: bool
    position_id: str | None
    fill_price: float | None
    error: str | None = None


@dataclass
class CloseFillEvent:
    success: bool
    position_id: str
    exit_price: float
    realized_pnl: float
    error: str | None = None


@dataclass
class PositionSnapshot:
    positions: list[dict[str, Any]] = field(default_factory=list)
    realized: float = 0.0
    unrealized: float = 0.0
    total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "positions": self.positions,
            "realized": self.realized,
            "unrealized": self.unrealized,
            "total": self.total,
        }


# Back-compat aliases while en1gma callers migrate to candidate_C vocabulary.
OrderResult = FillEvent
ExitResult = CloseFillEvent


@runtime_checkable
class BrokerAdapter(Protocol):
    """Minimal contract every broker must honour."""

    def submit_intent(self, intent: OrderIntent) -> FillEvent: ...

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        entry_price: float,
    ) -> FillEvent: ...

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "exit",
    ) -> CloseFillEvent: ...

    def snapshot(self) -> PositionSnapshot: ...

    def halt_all(self, halt_id: str) -> int: ...

    def get_total_pnl(self) -> dict[str, float]: ...
