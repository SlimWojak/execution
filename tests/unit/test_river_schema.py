"""River schema tests (TR01-TR04)."""

import os
from pathlib import Path

import pandas as pd
import pytest

from execution_rail.river.schema import (
    CANONICAL_PAIRS,
    RAW_COLUMNS,
    compute_bar_hashes,
    get_river_root,
    validate_raw_bars,
)
from execution_rail.river.synthetic import SyntheticRiver


def test_tr01_canonical_pairs():
    assert CANONICAL_PAIRS == frozenset(
        {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"}
    )


def test_tr02_validate_raw_bars_valid():
    synth = SyntheticRiver(seed_prefix="tr02")
    start = pd.Timestamp("2026-01-06 12:00", tz="UTC").to_pydatetime()
    end = pd.Timestamp("2026-01-06 13:00", tz="UTC").to_pydatetime()
    df = synth.generate_raw_bars("EURUSD", start, end)
    assert validate_raw_bars(df) == []


def test_tr03_missing_column_raises_inv_river():
    synth = SyntheticRiver(seed_prefix="tr03")
    start = pd.Timestamp("2026-01-06 12:00", tz="UTC").to_pydatetime()
    end = pd.Timestamp("2026-01-06 12:30", tz="UTC").to_pydatetime()
    df = synth.generate_raw_bars("EURUSD", start, end)
    df = df.drop(columns=["bar_hash"])
    errors = validate_raw_bars(df)
    assert any("INV-RIVER" in e for e in errors)


def test_tr04_river_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("RIVER_ROOT", str(tmp_path / "x"))
    assert get_river_root() == Path(str(tmp_path / "x"))


def test_compute_bar_hashes_deterministic():
    synth = SyntheticRiver(seed_prefix="hash")
    start = pd.Timestamp("2026-01-06 12:00", tz="UTC").to_pydatetime()
    end = pd.Timestamp("2026-01-06 12:05", tz="UTC").to_pydatetime()
    df = synth.generate_raw_bars("EURUSD", start, end)
    h1 = compute_bar_hashes(df)
    h2 = compute_bar_hashes(df)
    assert h1.equals(h2)
    assert len(h1) == len(df)
