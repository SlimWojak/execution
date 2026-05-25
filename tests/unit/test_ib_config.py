"""IBKR config unit tests (Brief 2 TI01-TI05)."""

from __future__ import annotations

import os

import pytest

from execution_rail.ib.config import IBKRConfig, IBKRMode


@pytest.fixture(autouse=True)
def _clean_ibkr_env(monkeypatch):
    for key in (
        "IBKR_MODE", "IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID",
        "IBKR_ALLOW_LIVE", "IBKR_FILL_TIMEOUT_SEC",
    ):
        monkeypatch.delenv(key, raising=False)


def test_ti01_from_env_no_env_defaults_mock():
    config = IBKRConfig.from_env()
    assert config.mode == IBKRMode.MOCK


def test_ti02_paper_mode_env(monkeypatch):
    monkeypatch.setenv("IBKR_MODE", "PAPER")
    config = IBKRConfig.from_env()
    assert config.mode == IBKRMode.PAPER
    assert config.port == 4002
    assert config.expected_account_prefix == "DU"
    assert config.client_id == 2


def test_ti03_live_without_allow_live_fails():
    config = IBKRConfig(mode=IBKRMode.LIVE, allow_live=False)
    valid, errors = config.validate_startup()
    assert not valid
    assert any("INV-IBKR-PAPER-GUARD-1" in e for e in errors)


def test_ti04_validate_du_account_paper():
    config = IBKRConfig(mode=IBKRMode.PAPER)
    valid, _ = config.validate_account("DU1234567")
    assert valid


def test_ti05_validate_live_account_rejected_in_paper():
    config = IBKRConfig(mode=IBKRMode.PAPER)
    valid, error = config.validate_account("U9999999")
    assert not valid
    assert error and "INV-IBKR-ACCOUNT-CHECK-1" in error
