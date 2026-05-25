"""
BrokerAdapter Protocol — sole broker contract for the execution rail.

Every broker implementation (PaperBroker, IBPaperAdapter, IBLiveAdapter)
must satisfy this Protocol. Strategy and orchestrator code depend on the
Protocol type, never a concrete class.

INVARIANT: INV-BROKER-PROTOCOL-IS-CONTRACT
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class OrderResult:
    success: bool
    position_id: str | None
    fill_price: float | None
    error: str | None = None


@dataclass
class ExitResult:
    success: bool
    position_id: str
    exit_price: float
    realized_pnl: float
    error: str | None = None


@runtime_checkable
class BrokerAdapter(Protocol):
    """Minimal contract every broker must honour."""

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        entry_price: float,
    ) -> OrderResult: ...

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "exit",
    ) -> ExitResult: ...

    def halt_all(self, halt_id: str) -> int: ...

    def get_total_pnl(self) -> dict[str, float]: ...
