"""
Paper broker adapter — immediate fills, P&L tracking.

Lifted from: en1gma/console/execution/broker_adapter.py
Origin: phoenix/execution/broker_stub.py (proven, lean extraction)

Satisfies BrokerAdapter Protocol (broker_protocol.py).

P&L v0: No fees, no slippage, deterministic fills.

INVARIANT: INV-GOV-HALT-BEFORE-ACTION
"""

from __future__ import annotations

from datetime import UTC, datetime

from .broker_protocol import (
    CloseFillEvent,
    ExitResult,
    FillEvent,
    OrderIntent,
    OrderResult,
    PositionSnapshot,
)
from .halt_types import HaltChecker
from .position import Position, PositionState


VALID_DIRECTIONS = frozenset({"LONG", "SHORT"})


def _normalize_direction(direction: str) -> str:
    normalized = direction.upper()
    if normalized not in VALID_DIRECTIONS:
        raise ValueError(f"direction must be LONG or SHORT, got {direction!r}")
    return normalized


class PaperBroker:
    """Paper broker for testing and shadow execution."""

    def __init__(self, halt_signal: HaltChecker):
        self._halt = halt_signal
        self._positions: dict[str, Position] = {}
        self._counter = 0

    def _check_halt(self) -> None:
        self._halt.check()

    def submit_intent(self, intent: OrderIntent) -> FillEvent:
        return self.open_position(
            intent.symbol,
            intent.direction,
            intent.size,
            intent.entry_price,
        )

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        entry_price: float,
    ) -> FillEvent:
        """Open a new position with immediate fill."""
        self._check_halt()
        direction = _normalize_direction(direction)
        self._counter += 1
        now = datetime.now(UTC)
        position_id = f"POS-{now.strftime('%Y%m%d%H%M%S')}-{self._counter:04d}"

        position = Position(
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            size=size,
        )
        position.fill(entry_price, size)
        self._positions[position_id] = position

        return OrderResult(
            success=True,
            position_id=position_id,
            fill_price=entry_price,
        )

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "exit",
    ) -> CloseFillEvent:
        """Close a position at the given price."""
        self._check_halt()
        position = self._positions.get(position_id)
        if position is None:
            return CloseFillEvent(
                success=False, position_id=position_id,
                exit_price=0.0, realized_pnl=0.0,
                error=f"not found: {position_id}",
            )
        position.close(exit_price, reason)
        return CloseFillEvent(
            success=True, position_id=position_id,
            exit_price=exit_price, realized_pnl=position.realized_pnl,
        )

    def snapshot(self) -> PositionSnapshot:
        pnl = self.get_total_pnl()
        return PositionSnapshot(
            positions=[p.to_dict() for p in self._positions.values()],
            realized=pnl["realized"],
            unrealized=pnl["unrealized"],
            total=pnl["total"],
        )

    def halt_all(self, halt_id: str) -> int:
        count = 0
        for p in self._positions.values():
            if p.state not in (PositionState.CLOSED, PositionState.HALTED):
                p.halt(halt_id)
                count += 1
        return count

    def get_total_pnl(self) -> dict[str, float]:
        realized = sum(p.realized_pnl for p in self._positions.values())
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return {"realized": realized, "unrealized": unrealized, "total": realized + unrealized}


__all__ = [
    "CloseFillEvent",
    "ExitResult",
    "FillEvent",
    "OrderIntent",
    "OrderResult",
    "PaperBroker",
    "PositionSnapshot",
]
