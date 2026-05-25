"""Env-gated IB integration tests (Brief 2 TI12-TI13)."""

from __future__ import annotations

import os

import pytest

from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter

pytestmark = pytest.mark.integration

FOREX_LOT = 20_000.0


class _NoHalt:
    def check(self) -> None:
        return None


def _integration_enabled() -> bool:
    return os.getenv("IBKR_INTEGRATION_TEST", "").strip() == "1"


@pytest.fixture
def paper_adapter():
    if not _integration_enabled():
        pytest.skip("IBKR_INTEGRATION_TEST=1 not set")
    config = IBKRConfig.from_env()
    if config.mode != IBKRMode.PAPER:
        pytest.skip("IBKR_MODE must be PAPER for integration tests")
    adapter = IBPaperAdapter(_NoHalt(), config)
    yield adapter
    adapter.disconnect()


def test_ti12_open_fill(paper_adapter):
    result = paper_adapter.open_position("EURUSD", "LONG", FOREX_LOT, 0.0)
    assert result.success
    assert result.fill_price and result.fill_price > 0
    if result.position_id:
        paper_adapter.close_position(result.position_id, result.fill_price)


def test_ti13_round_trip(paper_adapter):
    open_result = paper_adapter.open_position("EURUSD", "LONG", FOREX_LOT, 0.0)
    assert open_result.success and open_result.position_id
    close_result = paper_adapter.close_position(
        open_result.position_id,
        open_result.fill_price or 0.0,
    )
    assert close_result.success
    assert close_result.realized_pnl is not None
