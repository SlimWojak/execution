"""Unit tests — BrokerAdapter Protocol + factory (Brief 1 T5)."""

from __future__ import annotations

from typing import get_type_hints

import pytest

from execution_rail.broker_adapter import OrderResult as AdapterOrderResult
from execution_rail.broker_adapter import PaperBroker
from execution_rail.broker_factory import build_broker
from execution_rail.broker_protocol import (
    BrokerAdapter,
    CloseFillEvent,
    ExitResult,
    FillEvent,
    OrderIntent,
    OrderResult,
    PositionSnapshot,
)
from execution_rail.halt_types import LocalHaltSignal
from execution_rail.ib.supervisor import IBKRSupervisor
from execution_rail.mode import OperatingMode
from execution_rail.mode_promotion import ModePromotionError, grant_mode


class _NoHalt:
    def check(self) -> None:
        return None


class DummyBroker:
    """Minimal third-party plug-in for Protocol isinstance check."""

    def submit_intent(self, intent: OrderIntent) -> FillEvent:
        return self.open_position(
            intent.symbol,
            intent.direction,
            intent.size,
            intent.entry_price,
        )

    def open_position(self, symbol: str, direction: str, size: float, entry_price: float) -> FillEvent:
        return FillEvent(success=True, position_id="D-1", fill_price=entry_price)

    def close_position(self, position_id: str, exit_price: float, reason: str = "exit") -> CloseFillEvent:
        return CloseFillEvent(success=True, position_id=position_id, exit_price=exit_price, realized_pnl=0.0)

    def snapshot(self) -> PositionSnapshot:
        return PositionSnapshot()

    def halt_all(self, halt_id: str) -> int:
        return 0

    def get_total_pnl(self) -> dict[str, float]:
        return {"realized": 0.0, "unrealized": 0.0, "total": 0.0}


@pytest.fixture
def halt():
    return _NoHalt()


def test_tb01_paper_broker_satisfies_protocol(halt):
    assert isinstance(PaperBroker(halt), BrokerAdapter) is True


def test_tb02_build_broker_paper(halt, monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(tmp_path / "mode_grants.jsonl"))
    grant_mode(OperatingMode.PAPER, reason="test", grantor="pytest")
    from execution_rail.ib.paper_adapter import IBPaperAdapter

    broker = build_broker(OperatingMode.PAPER, halt)
    assert isinstance(broker, IBPaperAdapter)


def test_tb03_build_broker_shadow(halt):
    broker = build_broker(OperatingMode.SHADOW, halt)
    assert isinstance(broker, PaperBroker)


def test_tb04_build_broker_test(halt):
    broker = build_broker(OperatingMode.TEST, halt)
    assert isinstance(broker, PaperBroker)


def test_tb05_build_broker_live_raises(halt):
    with pytest.raises(NotImplementedError, match="LIVE broker"):
        build_broker(OperatingMode.LIVE, halt)


def test_tb06_build_broker_return_annotation():
    assert get_type_hints(build_broker)["return"] is BrokerAdapter


def test_tb07_order_result_import_identity():
    assert OrderResult is AdapterOrderResult
    from execution_rail.broker_protocol import OrderResult as ProtoOrderResult
    assert ProtoOrderResult is OrderResult
    assert OrderResult is FillEvent
    assert ExitResult is CloseFillEvent


def test_tb08_dummy_broker_plugin_path():
    assert isinstance(DummyBroker(), BrokerAdapter) is True


def test_tb09_submit_intent_and_snapshot(halt):
    broker = PaperBroker(halt)
    fill = broker.submit_intent(OrderIntent("EURUSD", "LONG", 1.0, 1.1))
    assert fill.success
    snapshot = broker.snapshot()
    assert snapshot.total == 0.0
    assert len(snapshot.positions) == 1


def test_tb10_invalid_direction_rejected(halt):
    broker = PaperBroker(halt)
    with pytest.raises(ValueError, match="LONG or SHORT"):
        broker.open_position("EURUSD", "SIDEWAYS", 1.0, 1.1)


def test_tb11_paper_requires_mode_grant(halt, monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(tmp_path / "missing.jsonl"))
    with pytest.raises(ModePromotionError):
        build_broker(OperatingMode.PAPER, halt)


def test_tb12_supervisor_rejected_for_shadow(halt):
    supervisor = IBKRSupervisor(halt_signal=LocalHaltSignal())
    with pytest.raises(ValueError, match="supervisor is only valid"):
        build_broker(OperatingMode.SHADOW, halt, supervisor=supervisor)
