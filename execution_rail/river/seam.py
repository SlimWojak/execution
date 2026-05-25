"""
River seam — staging JSONL → immutable daily parquet.

Forex day close (17:00 NY): consolidate staging into write-once parquet.
INV-RIVER-IMMUTABLE enforced.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .schema import RAW_BAR_SCHEMA, RAW_COLUMNS, compute_bar_hashes, get_river_root, validate_raw_bars

logger = logging.getLogger(__name__)


def staging_path(river_root: Path, pair: str, dt: datetime) -> Path:
    return river_root / pair / ".staging" / f"{dt.strftime('%Y-%m-%d')}.jsonl"


def parquet_path(river_root: Path, pair: str, dt: datetime) -> Path:
    return (
        river_root / pair / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}.parquet"
    )


def consolidate_day(
    pair: str,
    date: datetime,
    *,
    river_root: Path | None = None,
) -> int:
    """Consolidate staging JSONL for a date into daily parquet.

    INV-RIVER-IMMUTABLE: If daily parquet already exists, skip (returns 0).
    """
    root = river_root or get_river_root()
    staging_file = staging_path(root, pair, date)
    if not staging_file.exists():
        return 0

    parquet_file = parquet_path(root, pair, date)
    if parquet_file.exists():
        logger.debug("parquet_exists_skip path=%s", parquet_file)
        return 0

    rows: list[dict] = []
    with open(staging_file) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    if not rows:
        return 0

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["knowledge_time"] = pd.to_datetime(df["knowledge_time"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

    # Drop optional staging-only columns before validation
    for col in ("raw_open",):
        if col in df.columns:
            df = df.drop(columns=[col])

    if "source" not in df.columns:
        df["source"] = "ibkr"
    if "bar_hash" not in df.columns:
        df["bar_hash"] = compute_bar_hashes(df)

    errors = validate_raw_bars(df)
    if errors:
        logger.error("consolidation_validation_failed date=%s errors=%s", date, errors)
        return 0

    parquet_file.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df[RAW_COLUMNS], schema=RAW_BAR_SCHEMA, preserve_index=False)
    pq.write_table(table, parquet_file)

    logger.info("consolidated path=%s bars=%d", parquet_file, len(df))
    return len(df)


def consolidate_all_pending(
    pair: str,
    *,
    river_root: Path | None = None,
) -> int:
    """Consolidate all pending staging files for a pair."""
    root = river_root or get_river_root()
    staging_dir = root / pair / ".staging"
    if not staging_dir.exists():
        return 0

    total = 0
    for f in sorted(staging_dir.glob("*.jsonl")):
        try:
            date = datetime.strptime(f.stem, "%Y-%m-%d")
        except ValueError:
            continue
        total += consolidate_day(pair, date, river_root=root)
    return total


def write_parquet_immutable(path: Path, df: pd.DataFrame) -> int:
    """Write parquet if absent. Raises if path exists (INV-RIVER-IMMUTABLE)."""
    if path.exists():
        raise FileExistsError(f"INV-RIVER-IMMUTABLE: {path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, schema=RAW_BAR_SCHEMA, preserve_index=False)
    pq.write_table(table, path)
    return len(df)
