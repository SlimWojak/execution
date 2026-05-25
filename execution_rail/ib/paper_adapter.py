"""
IB paper adapter — real IB Gateway fills implementing BrokerAdapter.

INVARIANTS:
  INV-GOV-HALT-BEFORE-ACTION
  INV-IBKR-PAPER-GUARD-1
  INV-IBKR-ACCOUNT-CHECK-1
  INV-IBKR-CLIENT-ISOLATION
  INV-IBKR-RECONNECT-1
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from execution_rail.broker_protocol import ExitResult, OrderResult
from execution_rail.halt_types import HaltChecker
from execution_rail.position import Position, PositionState

from .client_id import ClientIdRole, allocate_client_id
from .config import IBKRConfig, IBKRMode, ReconnectTracker
from .orders import IBOrder, IBOrderSide, IBOrderStatus
from .real_client import RealIBKRClient

if TYPE_CHECKING:
    from .supervisor import IBKRSupervisor


class IBPaperAdapter:
    """Real IB paper-account adapter implementing BrokerAdapter."""

    def __init__(
        self,
        halt_signal: HaltChecker,
        config: IBKRConfig,
        fill_timeout_sec: float | None = None,
        supervisor: IBKRSupervisor | None = None,
    ) -> None:
        if config.mode != IBKRMode.PAPER:
            raise ValueError(f"IBPaperAdapter requires PAPER mode, got {config.mode}")
        self._halt = halt_signal
        self._halt_signaler = halt_signal if hasattr(halt_signal, "signal_local") else None
        self._config = config
        self._config.client_id = allocate_client_id(ClientIdRole.BROKER)
        self._fill_timeout = fill_timeout_sec or config.fill_timeout_sec
        self._client = RealIBKRClient(self._config)
        self._supervisor = supervisor
        self._positions: dict[str, Position] = {}
        self._quantities: dict[str, float] = {}
        self._counter = 0
        self._connected = False

    def _check_halt(self) -> None:
        self._halt.check()

    def _pulse_heartbeat(self) -> None:
        if self._supervisor and self._supervisor.heartbeat:
            self._supervisor.heartbeat.beat()

    def _ensure_connected(self) -> None:
        if self._connected and self._client.connected:
            return

        tracker = ReconnectTracker(config=self._config.reconnect)
        tracker.begin()
        last_error: Exception | None = None

        while True:
            try:
                if self._client.connect():
                    self._connected = True
                    tracker.record_success()
                    return
            except Exception as exc:
                last_error = exc

            should_continue, delay = tracker.register_attempt()
            if not should_continue:
                if self._halt_signaler:
                    self._halt_signaler.signal_local(
                        "ib_reconnect", "max_attempts_exceeded"
                    )
                raise ConnectionError(
                    f"IB Gateway connection failed after reconnect backoff: {last_error}"
                ) from last_error
            time.sleep(delay)

    @staticmethod
    def _direction_to_side(direction: str, opening: bool) -> IBOrderSide:
        direction = direction.upper()
        if opening:
            return IBOrderSide.BUY if direction == "LONG" else IBOrderSide.SELL
        return IBOrderSide.SELL if direction == "LONG" else IBOrderSide.BUY

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        entry_price: float,
    ) -> OrderResult:
        self._check_halt()
        self._ensure_connected()
        self._pulse_heartbeat()

        ib_order = IBOrder(
            symbol=symbol,
            side=self._direction_to_side(direction, opening=True),
            quantity=size,
        )
        result = self._client.submit_order(ib_order, self._fill_timeout)
        self._pulse_heartbeat()

        if not result.success or result.status != IBOrderStatus.FILLED:
            return OrderResult(
                success=False,
                position_id=None,
                fill_price=result.fill_price,
                error=result.message or "; ".join(result.errors),
            )

        self._counter += 1
        now = datetime.now(UTC)
        position_id = f"POS-{now.strftime('%Y%m%d%H%M%S')}-{self._counter:04d}"
        position = Position(
            position_id=position_id,
            symbol=symbol,
            direction=direction.upper(),
            size=size,
        )
        fill_price = result.fill_price or entry_price
        position.fill(fill_price, size)
        self._positions[position_id] = position
        self._quantities[position_id] = size

        return OrderResult(
            success=True,
            position_id=position_id,
            fill_price=fill_price,
        )

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "exit",
    ) -> ExitResult:
        self._check_halt()
        position = self._positions.get(position_id)
        if position is None:
            return ExitResult(
                success=False,
                position_id=position_id,
                exit_price=0.0,
                realized_pnl=0.0,
                error=f"not found: {position_id}",
            )

        self._ensure_connected()
        self._pulse_heartbeat()
        quantity = self._quantities.get(position_id, position.size)
        ib_order = IBOrder(
            symbol=position.symbol,
            side=self._direction_to_side(position.direction, opening=False),
            quantity=quantity,
        )
        result = self._client.submit_order(ib_order, self._fill_timeout)
        self._pulse_heartbeat()

        if not result.success:
            return ExitResult(
                success=False,
                position_id=position_id,
                exit_price=0.0,
                realized_pnl=0.0,
                error=result.message or "; ".join(result.errors),
            )

        close_price = result.fill_price or exit_price
        position.close(close_price, reason)
        return ExitResult(
            success=True,
            position_id=position_id,
            exit_price=close_price,
            realized_pnl=position.realized_pnl,
        )

    def halt_all(self, halt_id: str) -> int:
        count = 0
        for pos in self._positions.values():
            if pos.state not in (PositionState.CLOSED, PositionState.HALTED):
                pos.halt(halt_id)
                count += 1
        if self._connected:
            self._client.disconnect()
            self._connected = False
        return count

    def get_total_pnl(self) -> dict[str, float]:
        realized = sum(p.realized_pnl for p in self._positions.values())
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        if self._connected:
            account = self._client.get_account()
            unrealized = account.unrealized_pnl
        return {"realized": realized, "unrealized": unrealized, "total": realized + unrealized}

    def disconnect(self) -> None:
        if self._connected:
            self._client.disconnect()
            self._connected = False
