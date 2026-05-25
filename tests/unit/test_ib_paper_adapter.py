"""IBPaperAdapter unit tests (Brief 2 TI06-TI07)."""

from __future__ import annotations

import pytest

from execution_rail.halt_types import HaltError
from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter


class _NoHalt:
    def check(self) -> None:
        return None


class _Halted:
    def check(self) -> None:
        raise HaltError("halt active")


def test_ti06_mock_config_rejected():
    config = IBKRConfig(mode=IBKRMode.MOCK)
    with pytest.raises(ValueError, match="PAPER mode"):
        IBPaperAdapter(_NoHalt(), config)


def test_ti07_halt_before_connect():
    config = IBKRConfig(mode=IBKRMode.PAPER)
    adapter = IBPaperAdapter(_Halted(), config)
    with pytest.raises(HaltError):
        adapter.open_position("EURUSD", "LONG", 20000.0, 1.1)
