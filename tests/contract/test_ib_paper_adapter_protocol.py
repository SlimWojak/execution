"""IBPaperAdapter contract tests (Brief 2 TI08-TI11)."""

from __future__ import annotations

import pytest

from execution_rail.broker_adapter import PaperBroker
from execution_rail.broker_factory import build_broker
from execution_rail.broker_protocol import BrokerAdapter
from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter
from execution_rail.mode import OperatingMode


class _NoHalt:
    def check(self) -> None:
        return None


@pytest.fixture
def paper_config():
    return IBKRConfig(mode=IBKRMode.PAPER)


def test_ti08_protocol_satisfied(paper_config):
    adapter = IBPaperAdapter(_NoHalt(), paper_config)
    assert isinstance(adapter, BrokerAdapter)


def test_ti09_factory_paper_returns_ib_adapter(monkeypatch):
    monkeypatch.setenv("IBKR_MODE", "PAPER")
    broker = build_broker(OperatingMode.PAPER, _NoHalt())
    assert isinstance(broker, IBPaperAdapter)


def test_ti10_factory_shadow_returns_paper_broker():
    broker = build_broker(OperatingMode.SHADOW, _NoHalt())
    assert isinstance(broker, PaperBroker)


def test_ti11_factory_test_returns_paper_broker():
    broker = build_broker(OperatingMode.TEST, _NoHalt())
    assert isinstance(broker, PaperBroker)
