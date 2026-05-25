"""River seam tests (TR11-TR13)."""

import json
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from execution_rail.river.schema import validate_raw_bars
from execution_rail.river.seam import consolidate_day, parquet_path, staging_path
from execution_rail.river.synthetic import SyntheticRiver


def _write_staging(root: Path, pair: str, date: datetime, n_bars: int = 100) -> None:
    synth = SyntheticRiver(seed_prefix="seam")
    start = datetime(date.year, date.month, date.day, 0, 0)
    end = datetime(date.year, date.month, date.day, n_bars // 60 + 2, n_bars % 60)
    from datetime import UTC, timedelta

    start = start.replace(tzinfo=UTC)
    end = start + timedelta(minutes=n_bars)
    df = synth.generate_raw_bars(pair, start, end)
    path = staging_path(root, pair, date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for _, row in df.head(n_bars).iterrows():
            rec = {
                "timestamp": row["timestamp"].isoformat(),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "source": row["source"],
                "knowledge_time": row["knowledge_time"].isoformat(),
            }
            f.write(json.dumps(rec) + "\n")


def test_tr11_seam_consolidates_staging_to_parquet(tmp_path):
    pair = "EURUSD"
    date = datetime(2026, 1, 6)
    _write_staging(tmp_path, pair, date, n_bars=100)
    written = consolidate_day(pair, date, river_root=tmp_path)
    assert written == 100
    pq_file = parquet_path(tmp_path, pair, date)
    assert pq_file.exists()
    table = pq.read_table(pq_file)
    assert table.num_rows == 100
    df = table.to_pandas()
    assert validate_raw_bars(df) == []


def test_tr12_seam_idempotent_second_call_noop(tmp_path):
    pair = "EURUSD"
    date = datetime(2026, 1, 6)
    _write_staging(tmp_path, pair, date, n_bars=50)
    first = consolidate_day(pair, date, river_root=tmp_path)
    second = consolidate_day(pair, date, river_root=tmp_path)
    assert first == 50
    assert second == 0


def test_tr13_seam_rejects_rewrite_existing_parquet(tmp_path):
    pair = "EURUSD"
    date = datetime(2026, 1, 6)
    _write_staging(tmp_path, pair, date, n_bars=10)
    consolidate_day(pair, date, river_root=tmp_path)
    pq_file = parquet_path(tmp_path, pair, date)
    assert pq_file.exists()
    # Second consolidate is no-op, not rewrite — immutability preserved
    assert consolidate_day(pair, date, river_root=tmp_path) == 0
    table = pq.read_table(pq_file)
    assert table.num_rows == 10
