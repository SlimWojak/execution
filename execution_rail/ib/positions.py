"""IBKR position rows — broker account state, not internal Position FSM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class IBPosition:
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    account: str = ""
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def side(self) -> str:
        if self.quantity > 0:
            return "LONG"
        if self.quantity < 0:
            return "SHORT"
        return "FLAT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "side": self.side,
            "avg_cost": self.avg_cost,
            "unrealized_pnl": self.unrealized_pnl,
            "account": self.account,
        }


@dataclass
class IBPositionSnapshot:
    positions: list[IBPosition] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    account: str = ""

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions)

    def get_position(self, symbol: str) -> IBPosition | None:
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "positions": [p.to_dict() for p in self.positions],
            "timestamp": self.timestamp.isoformat(),
            "account": self.account,
            "total_unrealized_pnl": self.total_unrealized_pnl,
        }
