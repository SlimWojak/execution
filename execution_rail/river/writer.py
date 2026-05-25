"""
River Writer — IBKR historical data → daily parquet files.

Invariants:
    INV-RIVER-IMMUTABLE: Daily parquet files are write-once
    INV-RIVER-BITEMPORAL: Every bar carries knowledge_time
    INV-RIVER-SOURCE-TAG: source = 'ibkr'
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from execution_rail.ib.client_id import ClientIdRole, allocate_client_id

from .schema import (
    CANONICAL_PAIRS,
    RAW_BAR_SCHEMA,
    compute_bar_hashes,
    get_river_root,
    validate_raw_bars,
)

if TYPE_CHECKING:
    from ib_insync import IB

if "EventKit._metadata" in sys.modules:
    del sys.modules["EventKit._metadata"]
if "EventKit" in sys.modules:
    del sys.modules["EventKit"]

try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

logger = logging.getLogger(__name__)

IBKR_PACING_SECONDS = 11
IBKR_DEFAULT_PORT = 4002


class RiverWriter:
    """Fetches 1m bars from IBKR and writes daily parquet files."""

    def __init__(
        self,
        river_root: Path | None = None,
        ibkr_port: int = IBKR_DEFAULT_PORT,
    ) -> None:
        self._river_root = river_root or get_river_root()
        self._ibkr_port = ibkr_port
        self._last_request_time: float | None = None
        self._ib: IB | None = None
        self._client_id = allocate_client_id(ClientIdRole.DRILL)

    def parquet_path(self, pair: str, dt: datetime) -> Path:
        return (
            self._river_root / pair / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}.parquet"
        )

    def capture_all(self, lookback_days: int = 35) -> dict[str, int]:
        results: dict[str, int] = {}
        self._connect()
        try:
            for pair in sorted(CANONICAL_PAIRS):
                self._apply_pacing()
                try:
                    results[pair] = self._capture_pair(pair, lookback_days)
                except Exception:
                    logger.exception("pair_capture_failed pair=%s", pair)
                    results[pair] = 0
                    self._reconnect()
        finally:
            self._disconnect()
        return results

    def fetch_pair_day(self, pair: str, day: datetime) -> pd.DataFrame | None:
        """Fetch one calendar day of 1m bars for a pair."""
        self._connect()
        try:
            end = day.replace(tzinfo=UTC) + timedelta(days=1)
            start = day.replace(tzinfo=UTC)
            return self._fetch_bars(pair, start, end)
        finally:
            self._disconnect()

    def write_day_if_absent(self, pair: str, day: datetime, df: pd.DataFrame) -> int:
        path = self.parquet_path(pair, day)
        if path.exists():
            raise FileExistsError(f"INV-RIVER-IMMUTABLE: {path} already exists")
        df = df.copy()
        df["source"] = "ibkr"
        df["knowledge_time"] = pd.Timestamp.now(tz="UTC")
        df["bar_hash"] = compute_bar_hashes(df)
        errors = validate_raw_bars(df)
        if errors:
            raise ValueError(f"Validation failed: {errors}")
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(df, schema=RAW_BAR_SCHEMA, preserve_index=False)
        pq.write_table(table, path)
        return len(df)

    def _capture_pair(self, pair: str, lookback_days: int) -> int:
        if pair not in CANONICAL_PAIRS:
            raise ValueError(f"Non-canonical pair: {pair}")

        end = datetime.now(UTC)
        start = end - timedelta(days=lookback_days)
        df = self._fetch_bars(pair, start, end)
        if df is None or df.empty:
            return 0

        df["source"] = "ibkr"
        df["knowledge_time"] = pd.Timestamp.now(tz="UTC")
        df["bar_hash"] = compute_bar_hashes(df)

        errors = validate_raw_bars(df)
        if errors:
            raise ValueError(f"Validation failed for {pair}: {errors}")

        return self._write_daily_partitions(pair, df)

    def _fetch_bars(
        self,
        pair: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame | None:
        chunk_size = timedelta(days=2)
        chunks: list[pd.DataFrame] = []
        cur = end

        while cur > start:
            chunk_start = max(start, cur - chunk_size)
            duration = self._duration_str(chunk_start, cur)
            chunk = self._ibkr_request(pair, cur, duration)
            if chunk is not None and not chunk.empty:
                chunks.append(chunk)
            cur = chunk_start

        if not chunks:
            return None

        combined = pd.concat(chunks, ignore_index=True)
        start_ts = pd.Timestamp(start.replace(tzinfo=None), tz="UTC")
        combined = combined[combined["timestamp"] >= start_ts]
        return combined.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

    def _ibkr_request(
        self,
        pair: str,
        end_dt: datetime,
        duration: str,
    ) -> pd.DataFrame | None:
        from ib_insync import Forex

        if self._ib is None or not self._ib.isConnected():
            self._connect()
        assert self._ib is not None

        contract = Forex(pair)
        self._ib.qualifyContracts(contract)
        self._apply_pacing()

        try:
            bars = self._ib.reqHistoricalData(
                contract,
                endDateTime=end_dt,
                durationStr=duration,
                barSizeSetting="1 min",
                whatToShow="MIDPOINT",
                useRTH=False,
                formatDate=1,
                timeout=30,
            )
        except Exception:
            logger.exception("ibkr_request_error pair=%s duration=%s", pair, duration)
            return None

        if not bars:
            return None

        return pd.DataFrame(
            [
                {
                    "timestamp": pd.to_datetime(bar.date, utc=True),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
                for bar in bars
            ]
        )

    def _write_daily_partitions(self, pair: str, df: pd.DataFrame) -> int:
        df = df.copy()
        df["_date"] = df["timestamp"].dt.date
        written = 0

        for date_val, group in df.groupby("_date"):
            path = self.parquet_path(pair, date_val)
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            out = group.drop(columns=["_date"]).sort_values("timestamp").reset_index(drop=True)
            table = pa.Table.from_pandas(out, schema=RAW_BAR_SCHEMA, preserve_index=False)
            pq.write_table(table, path)
            written += len(out)

        return written

    def _connect(self) -> None:
        from ib_insync import IB

        self._ib = IB()
        logger.info(
            "ibkr_connecting port=%d client_id=%d", self._ibkr_port, self._client_id
        )
        self._ib.connect(
            "127.0.0.1", self._ibkr_port, clientId=self._client_id, timeout=15
        )
        if not self._ib.isConnected():
            raise ConnectionError("IBKR Gateway not reachable")

    def _disconnect(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()

    def _reconnect(self) -> None:
        self._disconnect()
        time.sleep(2)
        try:
            self._connect()
        except Exception:
            logger.exception("reconnect_failed")

    def _apply_pacing(self) -> None:
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < IBKR_PACING_SECONDS:
                time.sleep(IBKR_PACING_SECONDS - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def _duration_str(start: datetime, end: datetime) -> str:
        days = (end - start).days
        if days <= 1:
            return "1 D"
        if days <= 7:
            return f"{days} D"
        weeks = (days // 7) + 1
        return f"{weeks} W"
