"""Mode-promotion ledger tests."""

import pytest

from execution_rail.mode import OperatingMode
from execution_rail.mode_promotion import (
    ModePromotionError,
    assert_mode_granted,
    grant_mode,
    latest_grant,
)


def test_mode_grant_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(tmp_path / "mode_grants.jsonl"))
    grant_mode(OperatingMode.PAPER, reason="operator approved", grantor="G")

    grant = assert_mode_granted(OperatingMode.PAPER)

    assert grant["mode"] == "PAPER"
    assert grant["reason"] == "operator approved"
    assert grant["grantor"] == "G"
    assert latest_grant(OperatingMode.PAPER) == grant


def test_mode_grant_required(monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(tmp_path / "missing.jsonl"))

    with pytest.raises(ModePromotionError, match="requires a promotion grant"):
        assert_mode_granted(OperatingMode.PAPER)
