"""Supervised PAPER session tests."""

import pytest

from execution_rail.halt_types import LocalHaltSignal
from execution_rail.ib.session import supervised_paper_session
from execution_rail.mode_promotion import ModePromotionError


def test_supervised_paper_session_requires_grant(monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(tmp_path / "missing.jsonl"))

    with pytest.raises(ModePromotionError):
        with supervised_paper_session(LocalHaltSignal()):
            pass
