"""IBPaperAdapter unit tests (Brief 2 TI06-TI07)."""

from __future__ import annotations

import pytest

from execution_rail.halt_types import HaltError, LocalHaltSignal
from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter
from execution_rail.ib.supervisor import IBKRSupervisor


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


def test_config_client_id_is_not_mutated():
    config = IBKRConfig(mode=IBKRMode.PAPER, client_id=99)
    adapter = IBPaperAdapter(_NoHalt(), config)

    assert config.client_id == 99
    assert adapter._config.client_id == 2


def test_invalid_direction_rejected_before_connect():
    config = IBKRConfig(mode=IBKRMode.PAPER)
    adapter = IBPaperAdapter(_NoHalt(), config)

    with pytest.raises(ValueError, match="LONG or SHORT"):
        adapter.open_position("EURUSD", "SIDEWAYS", 20000.0, 1.1)


def test_disconnect_fast_path_escalates_halt():
    halt = LocalHaltSignal()
    supervisor = IBKRSupervisor(halt_signal=halt)
    config = IBKRConfig(mode=IBKRMode.PAPER)
    adapter = IBPaperAdapter(halt, config, supervisor=supervisor)

    adapter._handle_disconnect()

    assert halt.is_halted
    assert halt.last_source == "ib_supervisor"
