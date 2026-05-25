"""
Position lifecycle state machine — paper trading.

Lifted from: en1gma/console/execution/position.py
Origin: phoenix/execution/positions/paper.py (proven)

5-state lifecycle:
  PENDING → OPEN → CLOSED
  PENDING → OPEN → PARTIAL → CLOSED
  Any non-terminal → HALTED

INVARIANT: INV-EXEC-LIFECYCLE-1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class PositionState(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"
    HALTED = "HALTED"


VALID_TRANSITIONS: dict[PositionState, set[PositionState]] = {
    PositionState.PENDING: {PositionState.OPEN, PositionState.PARTIAL,
                            PositionState.CLOSED, PositionState.HALTED},
    PositionState.OPEN: {PositionState.PARTIAL, PositionState.CLOSED,
                         PositionState.HALTED},
    PositionState.PARTIAL: {PositionState.OPEN, PositionState.CLOSED,
                            PositionState.HALTED},
    PositionState.CLOSED: set(),
    PositionState.HALTED: set(),
}

TERMINAL = frozenset({PositionState.CLOSED, PositionState.HALTED})


class InvalidTransitionError(Exception):
    def __init__(self, from_state: PositionState, to_state: PositionState):
        super().__init__(
            f"INV-EXEC-LIFECYCLE-1: invalid {from_state.value} → {to_state.value}"
        )


@dataclass
class Position:
    """Paper position with lifecycle FSM and P&L tracking."""

    position_id: str
    symbol: str
    direction: str
    size: float
    state: PositionState = PositionState.PENDING

    entry_price: float | None = None
    exit_price: float | None = None
    filled_size: float = 0.0

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    def _transition(self, to_state: PositionState, reason: str = "") -> None:
        valid = VALID_TRANSITIONS.get(self.state, set())
        if to_state not in valid:
            raise InvalidTransitionError(self.state, to_state)
        self.state = to_state

    def fill(self, price: float, size: float) -> None:
        if self.state in TERMINAL:
            raise InvalidTransitionError(self.state, PositionState.OPEN)
        if self.entry_price is None:
            self.entry_price = price
        self.filled_size += size
        if self.filled_size >= self.size:
            self._transition(PositionState.OPEN, f"filled at {price}")
        elif self.state == PositionState.PENDING:
            self._transition(PositionState.PARTIAL, f"partial at {price}")

    def close(self, exit_price: float, reason: str = "exit") -> None:
        if self.state in TERMINAL:
            raise InvalidTransitionError(self.state, PositionState.CLOSED)
        self.exit_price = exit_price
        if self.entry_price is not None:
            mult = 1.0 if self.direction == "LONG" else -1.0
            self.realized_pnl = (exit_price - self.entry_price) * self.filled_size * mult
        self.unrealized_pnl = 0.0
        self._transition(PositionState.CLOSED, reason)

    def halt(self, halt_id: str) -> None:
        if self.state in TERMINAL:
            return
        self._transition(PositionState.HALTED, f"halt:{halt_id}")

    def update_unrealized(self, current_price: float) -> float:
        if self.state not in (PositionState.OPEN, PositionState.PARTIAL):
            return 0.0
        if self.entry_price is None:
            return 0.0
        mult = 1.0 if self.direction == "LONG" else -1.0
        self.unrealized_pnl = (current_price - self.entry_price) * self.filled_size * mult
        return self.unrealized_pnl

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "state": self.state.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "size": self.size,
            "filled_size": self.filled_size,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
        }
