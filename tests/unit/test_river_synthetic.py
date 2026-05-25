"""River synthetic tests (TR05-TR06)."""

from datetime import UTC, datetime

import pandas as pd

from execution_rail.river.schema import validate_raw_bars
from execution_rail.river.synthetic import SyntheticRiver


def test_tr05_synthetic_contiguous_schema_valid():
    synth = SyntheticRiver(seed_prefix="tr05")
    start = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)
    end = datetime(2026, 1, 6, 14, 0, tzinfo=UTC)
    df = synth.generate_raw_bars("EURUSD", start, end)
    assert not df.empty
    assert validate_raw_bars(df) == []
    diffs = df["timestamp"].diff().iloc[1:]
    assert (diffs == pd.Timedelta(minutes=1)).all()


def test_tr06_synthetic_deterministic():
    synth = SyntheticRiver(seed_prefix="tr06")
    start = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)
    end = datetime(2026, 1, 6, 13, 0, tzinfo=UTC)
    df1 = synth.generate_raw_bars("EURUSD", start, end)
    df2 = synth.generate_raw_bars("EURUSD", start, end)
    pd.testing.assert_frame_equal(df1, df2)
