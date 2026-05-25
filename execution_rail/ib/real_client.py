"""
IBKR real client — sole ib_insync importer.

INVARIANT: INV-IBKR-CLIENT-ISOLATION
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .account import AccountState
from .config import IBKRConfig, IBKRMode
from .orders import IBOrder, IBOrderResult, IBOrderSide, IBOrderStatus
from .positions import IBPosition, IBPositionSnapshot

logger = logging.getLogger(__name__)


@dataclass
class RealClientState:
    connected: bool = False
    account_id: str = ""
    port: int = 0
    gateway_version: str = ""


class RealIBKRClient:
    """Wraps ib_insync for IB Gateway connectivity."""

    def __init__(self, config: IBKRConfig) -> None:
        try:
            from ib_insync import IB  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "ib_insync not installed. Install with: pip install ib_insync"
            ) from exc

        valid, errors = config.validate_startup()
        if not valid:
            raise ValueError(f"Config validation failed: {errors}")

        self._config = config
        self._ib: Any = None
        self._state = RealClientState()

    @property
    def connected(self) -> bool:
        return self._state.connected and self._ib is not None and self._ib.isConnected()

    @property
    def account_id(self) -> str:
        return self._state.account_id

    def connect(self) -> bool:
        if self._config.mode == IBKRMode.MOCK:
            raise ValueError("RealIBKRClient cannot be used in MOCK mode")

        from ib_insync import IB

        self._ib = IB()
        try:
            self._ib.connect(
                host=self._config.host,
                port=self._config.port,
                clientId=self._config.client_id,
                timeout=self._config.timeout,
                readonly=self._config.readonly,
            )
            accounts = self._ib.managedAccounts()
            if not accounts:
                raise ConnectionError("No accounts returned from IBKR")

            self._state.account_id = accounts[0]
            self._state.port = self._config.port
            self._state.connected = True
            self._state.gateway_version = self._gateway_version()

            valid, error = self._config.validate_account(self._state.account_id)
            if not valid:
                self.disconnect()
                raise ValueError(error)

            self._ib.disconnectedEvent += self._handle_disconnect
            return True
        except Exception as exc:
            self._state.connected = False
            raise ConnectionError(f"Failed to connect to IBKR: {exc}") from exc

    def disconnect(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
        self._state.connected = False

    def _handle_disconnect(self) -> None:
        self._state.connected = False
        logger.warning("IBKR connection lost")

    def _gateway_version(self) -> str:
        try:
            if self._ib:
                return f"IB Gateway {self._ib.client.serverVersion()}"
        except Exception:
            pass
        return "unknown"

    def submit_order(
        self,
        order: IBOrder,
        fill_timeout_sec: float | None = None,
    ) -> IBOrderResult:
        timeout = fill_timeout_sec if fill_timeout_sec is not None else self._config.fill_timeout_sec

        if not self.connected:
            return IBOrderResult(
                success=False,
                order_id=order.order_id,
                status=IBOrderStatus.REJECTED,
                requested_quantity=order.quantity,
                message="Not connected to broker",
                errors=["Must connect before submitting orders"],
            )

        valid, errors = self._config.validate_order_context(
            self._state.account_id, self._state.port
        )
        if not valid:
            return IBOrderResult(
                success=False,
                order_id=order.order_id,
                status=IBOrderStatus.REJECTED,
                requested_quantity=order.quantity,
                message="Order context validation failed",
                errors=errors,
            )

        validation_errors = order.validate()
        if validation_errors:
            return IBOrderResult(
                success=False,
                order_id=order.order_id,
                status=IBOrderStatus.REJECTED,
                requested_quantity=order.quantity,
                message="Order validation failed",
                errors=validation_errors,
            )

        try:
            from ib_insync import Contract, MarketOrder

            contract = self._forex_contract(order.symbol)
            action = "BUY" if order.side == IBOrderSide.BUY else "SELL"
            ib_order = MarketOrder(action, order.quantity)
            trade = self._ib.placeOrder(contract, ib_order)
            self._wait_for_fill(trade, timeout)
            return self._trade_to_result(trade, order)
        except Exception as exc:
            logger.error("Order submission failed: %s", exc)
            return IBOrderResult(
                success=False,
                order_id=order.order_id,
                status=IBOrderStatus.REJECTED,
                requested_quantity=order.quantity,
                message=f"Order submission error: {exc}",
                errors=[str(exc)],
            )

    def _wait_for_fill(self, trade: Any, timeout_sec: float) -> None:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            status = trade.orderStatus.status
            if status == "Filled":
                return
            if status in ("Cancelled", "Inactive"):
                return
            self._ib.sleep(0.5)

    def _forex_contract(self, symbol: str) -> Any:
        from ib_insync import Contract

        if len(symbol) == 6:
            base, quote = symbol[:3], symbol[3:]
        else:
            base, quote = symbol, "USD"
        contract = Contract()
        contract.symbol = base
        contract.secType = "CASH"
        contract.currency = quote
        contract.exchange = "IDEALPRO"
        return contract

    def _trade_to_result(self, trade: Any, order: IBOrder) -> IBOrderResult:
        status_map = {
            "Submitted": IBOrderStatus.SUBMITTED,
            "Filled": IBOrderStatus.FILLED,
            "Cancelled": IBOrderStatus.CANCELLED,
            "Inactive": IBOrderStatus.REJECTED,
        }
        ib_status = trade.orderStatus.status
        status = status_map.get(ib_status, IBOrderStatus.SUBMITTED)

        fill_price = None
        filled_qty = 0.0
        if trade.fills:
            fill_price = trade.fills[-1].execution.avgPrice
            filled_qty = sum(f.execution.shares for f in trade.fills)

        success = status == IBOrderStatus.FILLED or (
            status == IBOrderStatus.SUBMITTED and filled_qty > 0
        )
        return IBOrderResult(
            success=success,
            order_id=order.order_id,
            status=status,
            broker_order_id=str(trade.order.orderId),
            fill_price=fill_price,
            filled_quantity=filled_qty,
            requested_quantity=order.quantity,
            message=f"Order {ib_status}",
        )

    def get_positions(self) -> IBPositionSnapshot:
        if not self.connected:
            return IBPositionSnapshot()
        try:
            ib_positions = self._ib.positions()
            positions = [self._to_ib_position(p) for p in ib_positions]
            return IBPositionSnapshot(
                positions=positions,
                account=self._state.account_id,
                timestamp=datetime.now(UTC),
            )
        except Exception as exc:
            logger.error("Failed to get positions: %s", exc)
            return IBPositionSnapshot()

    def get_position(self, symbol: str) -> IBPosition | None:
        return self.get_positions().get_position(symbol)

    def _to_ib_position(self, ib_pos: Any) -> IBPosition:
        symbol = f"{ib_pos.contract.symbol}{ib_pos.contract.currency}"
        return IBPosition(
            symbol=symbol,
            quantity=float(ib_pos.position),
            avg_cost=float(ib_pos.avgCost),
            market_price=float(ib_pos.avgCost),
            account=ib_pos.account,
        )

    def get_account(self) -> AccountState:
        if not self.connected:
            return AccountState(account_id="")
        try:
            summary = self._ib.accountSummary()
            values: dict[str, float] = {}
            for item in summary:
                if item.tag in {
                    "NetLiquidation",
                    "TotalCashValue",
                    "AvailableFunds",
                    "BuyingPower",
                    "MaintMarginReq",
                    "InitMarginReq",
                    "UnrealizedPnL",
                }:
                    values[item.tag] = float(item.value)
            return AccountState(
                account_id=self._state.account_id,
                net_liquidation=values.get("NetLiquidation", 0.0),
                total_cash=values.get("TotalCashValue", 0.0),
                available_funds=values.get("AvailableFunds", 0.0),
                buying_power=values.get("BuyingPower", 0.0),
                maintenance_margin=values.get("MaintMarginReq", 0.0),
                initial_margin=values.get("InitMarginReq", 0.0),
                unrealized_pnl=values.get("UnrealizedPnL", 0.0),
            )
        except Exception as exc:
            logger.error("Failed to get account: %s", exc)
            return AccountState(account_id=self._state.account_id)

    def health_check(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "account_id": self._state.account_id,
            "port": self._state.port,
            "gateway_version": self._state.gateway_version,
            "mode": self._config.mode.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
