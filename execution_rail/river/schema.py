"""
River schema — bar definitions, hash computation, validation.

Invariants:
    INV-RIVER-BITEMPORAL: Every bar carries world_time + knowledge_time
    INV-RIVER-SOURCE-TAG: Every bar carries source provenance forever
    INV-RIVER-IMMUTABLE: Raw parquet files are write-once, never modified
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa

CANONICAL_PAIRS: frozenset[str] = frozenset(
    {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "AUDUSD",
        "USDCAD",
    }
)

VALID_SOURCES: frozenset[str] = frozenset({"dukascopy", "ibkr"})

NEX_SOURCE_BOUNDARY = pd.Timestamp("2025-11-22", tz="UTC")


def get_river_root() -> Path:
    """Canonical river data location. Set RIVER_ROOT env var to override."""
    return Path(os.environ.get("RIVER_ROOT", str(Path.home() / "phoenix-river")))


RAW_COLUMNS: list[str] = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "knowledge_time",
    "bar_hash",
]

RAW_BAR_SCHEMA: pa.Schema = pa.schema(
    [
        ("timestamp", pa.timestamp("ns", tz="UTC")),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("source", pa.string()),
        ("knowledge_time", pa.timestamp("ns", tz="UTC")),
        ("bar_hash", pa.string()),
    ]
)


def compute_bar_hashes(df: pd.DataFrame) -> pd.Series:
    """Vectorized sha256(timestamp|open|high|low|close|volume|source)."""
    ts_str = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    payload = (
        ts_str
        + "|"
        + df["open"].map(repr)
        + "|"
        + df["high"].map(repr)
        + "|"
        + df["low"].map(repr)
        + "|"
        + df["close"].map(repr)
        + "|"
        + df["volume"].map(repr)
        + "|"
        + df["source"]
    )
    return payload.apply(lambda x: hashlib.sha256(x.encode()).hexdigest())


def validate_raw_bars(df: pd.DataFrame) -> list[str]:
    """Validate DataFrame against RAW_BAR_SCHEMA. Returns errors (empty = valid)."""
    errors: list[str] = []

    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        errors.append(f"INV-RIVER-SCHEMA: Missing columns: {sorted(missing)}")
        return errors

    if df.empty:
        errors.append("INV-RIVER-SCHEMA: Empty DataFrame")
        return errors

    if df["timestamp"].isna().any():
        errors.append(f"INV-RIVER-SCHEMA: Null timestamps: {df['timestamp'].isna().sum()}")

    if df["knowledge_time"].isna().any():
        errors.append(
            f"INV-RIVER-SCHEMA: Null knowledge_time: {df['knowledge_time'].isna().sum()}"
        )

    invalid_src = set(df["source"].unique()) - VALID_SOURCES
    if invalid_src:
        errors.append(f"INV-RIVER-SOURCE-TAG: Invalid source values: {invalid_src}")

    bad_hl = (df["high"] < df["low"]).sum()
    if bad_hl:
        errors.append(f"INV-RIVER-SCHEMA: high < low in {bad_hl} bars")

    dupes = df.duplicated(subset=["timestamp"]).sum()
    if dupes:
        errors.append(f"INV-RIVER-SCHEMA: Duplicate timestamps: {dupes}")

    if len(df) > 1:
        wt_diff = df["timestamp"].diff().iloc[1:]
        non_increasing = (wt_diff <= pd.Timedelta(0)).sum()
        if non_increasing:
            errors.append(
                f"INV-RIVER-MONOTONICITY: world_time not strictly increasing: "
                f"{non_increasing} violations"
            )

        kt_diff = df["knowledge_time"].diff().iloc[1:]
        kt_regress = (kt_diff < pd.Timedelta(0)).sum()
        if kt_regress:
            errors.append(
                f"INV-RIVER-MONOTONICITY: knowledge_time regression: {kt_regress} violations"
            )

    return errors
