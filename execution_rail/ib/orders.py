"""IBKR order types — renamed to avoid collision with broker_protocol.OrderResult."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class IBOrderType(str, Enum):
    MARKET = "MKT"


class IBOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class IBOrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class IBOrder:
    order_id: str = field(default_factory=lambda: f"ORD-{uuid.uuid4().hex[:8]}")
    symbol: str = ""
    order_type: IBOrderType = IBOrderType.MARKET
    side: IBOrderSide = IBOrderSide.BUY
    quantity: float = 0.0

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.symbol:
            errors.append("Symbol is required")
        if self.quantity <= 0:
            errors.append("Quantity must be positive")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class IBOrderResult:
    success: bool
    order_id: str
    status: IBOrderStatus
    broker_order_id: str | None = None
    fill_price: float | None = None
    filled_quantity: float = 0.0
    requested_quantity: float = 0.0
    message: str = ""
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def partial_fill_ratio(self) -> float:
        if self.requested_quantity <= 0:
            return 0.0
        return self.filled_quantity / self.requested_quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "status": self.status.value,
            "broker_order_id": self.broker_order_id,
            "fill_price": self.fill_price,
            "filled_quantity": self.filled_quantity,
            "requested_quantity": self.requested_quantity,
            "message": self.message,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
        }
