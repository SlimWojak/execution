"""
River Streamer — IBKR live 1m bar streaming to staging JSONL.

Invariants:
    INV-RIVER-IMMUTABLE: Daily parquet via seam consolidation only
    INV-RIVER-BITEMPORAL: knowledge_time = IBKR callback timestamp
    INV-NO-FORMING-CANDLE: Never emit incomplete bar
    INV-RIVER-SOURCE-TAG: source = 'ibkr'
    INV-RIVER-CLIENT-ID-1: clientId from allocator (RIVER=1)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from execution_rail.ib.client_id import ClientIdRole, allocate_client_id

from .market_hours import NY, is_forex_market_open
from .resubscribe import (
    CONSECUTIVE_GOOD_BARS_RESET,
    RESUBSCRIBE_BACKOFF_S,
    RESUBSCRIBE_MAX_ATTEMPTS,
    RiverResubscribeTracker,
)
from .schema import CANONICAL_PAIRS, get_river_root
from .seam import consolidate_all_pending, consolidate_day, parquet_path, staging_path
from .supervisor import RiverSupervisor

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

IBKR_DEFAULT_PORT = 4002
STALENESS_THRESHOLD_SECONDS = 120
WATCHDOG_INITIAL_TIMEOUT_S = 60


class RiverStreamer:
    """Live 1m bar streaming from IBKR to River staging JSONL."""

    def __init__(
        self,
        pair: str = "EURUSD",
        *,
        river_root: Path | None = None,
        ibkr_port: int = IBKR_DEFAULT_PORT,
        supervisor: RiverSupervisor | None = None,
    ) -> None:
        if pair not in CANONICAL_PAIRS:
            raise ValueError(f"Non-canonical pair: {pair}")

        self._pair = pair
        self._root = river_root or get_river_root()
        self._ibkr_port = ibkr_port
        self._supervisor = supervisor
        self._client_id = allocate_client_id(ClientIdRole.RIVER)
        self._resubscribe = RiverResubscribeTracker()
        self._ib: Any = None
        self._running = False
        self._last_bar_time: datetime | None = None
        self._last_bar_ts: pd.Timestamp | None = None
        self._consecutive_gaps = 0

        self._state = "STOPPED"
        self._connected = False
        self._subscribed = False
        self._bars_handle: Any = None
        self._subscribe_time: float | None = None

        self._bars_received = 0
        self._gaps_detected = 0
        self._last_bar_close: float | None = None
        self._known_timestamps: set[str] = set()
        self._session_start: datetime | None = None

    @property
    def staging_dir(self) -> Path:
        return self._root / self._pair / ".staging"

    @property
    def heartbeat_path(self) -> Path:
        return self._root / ".heartbeat.json"

    def staging_path_for(self, dt: datetime) -> Path:
        return staging_path(self._root, self._pair, dt)

    def parquet_path_for(self, dt: datetime) -> Path:
        return parquet_path(self._root, self._pair, dt)

    def get_status(self) -> dict[str, Any]:
        return {
            "state": self._state,
            "connected": self._connected,
            "subscribed": self._subscribed,
            "pair": self._pair,
            "last_bar_time": self._last_bar_time.isoformat() if self._last_bar_time else None,
            "last_update": datetime.now(UTC).isoformat(),
            "resubscribe_attempts": self._resubscribe.attempts,
            "bars_received": self._bars_received,
            "gaps_detected": self._gaps_detected,
            "consecutive_good_bars": self._resubscribe.consecutive_good_bars,
            "session_start": self._session_start.isoformat() if self._session_start else None,
        }

    def start(self) -> None:
        """Start streaming 1m bars from IBKR (blocks until stop)."""
        from ib_insync import IB

        self._state = "STARTED"
        self._session_start = datetime.now(UTC)
        self._update_heartbeat()

        self._ib = IB()
        logger.info(
            "streamer_connecting pair=%s port=%d client_id=%d",
            self._pair,
            self._ibkr_port,
            self._client_id,
        )
        self._ib.connect(
            "127.0.0.1", self._ibkr_port, clientId=self._client_id, timeout=15
        )

        self._connected = True
        self._ib.errorEvent += self._on_ib_error

        mdt = int(os.environ.get("IB_MARKET_DATA_TYPE", "1"))
        self._ib.reqMarketDataType(mdt)

        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self._subscribe()

        self._running = True
        self._update_heartbeat()

        try:
            while self._running:
                self._ib.sleep(1)
                self._check_watchdog()
        except KeyboardInterrupt:
            logger.info("streamer_interrupted pair=%s", self._pair)
        finally:
            self.stop()

    def _subscribe(self) -> None:
        from ib_insync import Forex

        contract = Forex(self._pair)
        self._ib.qualifyContracts(contract)

        self._bars_handle = self._ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting="1 min",
            whatToShow="MIDPOINT",
            useRTH=False,
            keepUpToDate=True,
            timeout=30,
        )

        if self._bars_handle and len(self._bars_handle) > 0:
            last_seed = self._bars_handle[-1]
            self._last_bar_time = datetime.now(UTC)
            self._last_bar_ts = pd.Timestamp(last_seed.date.timestamp(), unit="s", tz="UTC")

        self._persist_seed_bars()
        self._bars_handle.updateEvent += self._on_bar_update
        self._subscribed = True
        self._subscribe_time = time.monotonic()
        self._update_heartbeat()

    def _load_known_timestamps(self) -> None:
        if not self.staging_dir.exists():
            return
        for jsonl_path in self.staging_dir.glob("*.jsonl"):
            try:
                with open(jsonl_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                            if "timestamp" in row:
                                self._known_timestamps.add(row["timestamp"])
                        except (ValueError, json.JSONDecodeError):
                            continue
            except OSError:
                continue

    def _persist_seed_bars(self) -> None:
        if not self._bars_handle or len(self._bars_handle) < 2:
            return

        self._load_known_timestamps()
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        persisted = 0
        kt = datetime.now(UTC)

        for bar in self._bars_handle[:-1]:
            bar_ts = pd.Timestamp(bar.date.timestamp(), unit="s", tz="UTC")
            ts_key = bar_ts.isoformat()
            if ts_key in self._known_timestamps:
                continue

            bar_data = {
                "timestamp": ts_key,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "source": "ibkr",
                "knowledge_time": kt.isoformat(),
            }

            staging_file = self.staging_path_for(bar_ts.to_pydatetime())
            staging_file.parent.mkdir(parents=True, exist_ok=True)
            with open(staging_file, "a") as f:
                f.write(json.dumps(bar_data) + "\n")

            self._known_timestamps.add(ts_key)
            self._bars_received += 1
            persisted += 1

        last_seed = self._bars_handle[-2] if len(self._bars_handle) >= 2 else None
        if last_seed is not None:
            self._last_bar_close = float(last_seed.close)

        if persisted:
            logger.info("seed_bars_persisted pair=%s count=%d", self._pair, persisted)

    def stop(self) -> None:
        self._running = False
        self._subscribed = False
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
        self._connected = False
        self._state = "STOPPED"
        self._update_heartbeat()

    def _on_ib_error(
        self,
        reqId: int,  # noqa: N803
        errorCode: int,  # noqa: N803
        errorString: str,  # noqa: N803
        contract: Any = None,
    ) -> None:
        if errorCode in (2104, 2106, 2158):
            return
        logger.warning(
            "ib_error pair=%s code=%d msg=%s", self._pair, errorCode, errorString
        )
        if errorCode in (1100, 1300, 504, 502):
            self._connected = False
            self._subscribed = False
            if self._state != "STOPPED":
                self._state = "DEGRADED"
            self._update_heartbeat()

    def _on_bar_update(self, bars: Any, has_new_bar: bool) -> None:
        if not has_new_bar or not bars or len(bars) < 2:
            return

        bar = bars[-2]
        kt = datetime.now(UTC)
        bar_ts = pd.Timestamp(bar.date.timestamp(), unit="s", tz="UTC")
        ts_key = bar_ts.isoformat()

        if ts_key in self._known_timestamps:
            return
        if self._last_bar_ts is not None and bar_ts <= self._last_bar_ts:
            return
        self._known_timestamps.add(ts_key)

        if self._state != "STREAMING":
            self._state = "STREAMING"
            logger.info("streamer_first_bar pair=%s ts=%s", self._pair, bar_ts)

        if self._last_bar_ts is not None:
            expected_gap = pd.Timedelta(minutes=1)
            actual_gap = bar_ts - self._last_bar_ts
            if actual_gap > expected_gap * 2 and is_forex_market_open():
                missed = int(actual_gap.total_seconds() / 60) - 1
                self._consecutive_gaps += missed
                self._resubscribe.record_gap()
                self._gaps_detected += 1
            else:
                self._consecutive_gaps = 0
                self._resubscribe.record_good_bar()
        else:
            self._resubscribe.record_good_bar()

        self._last_bar_ts = bar_ts

        raw_open = float(bar.open)
        corrected_open = raw_open
        if self._last_bar_close is not None:
            delta = abs(raw_open - self._last_bar_close)
            if delta > 0.000005:
                corrected_open = self._last_bar_close

        bar_close = float(bar.close)
        self._last_bar_close = bar_close

        bar_data = {
            "timestamp": ts_key,
            "open": corrected_open,
            "high": float(bar.high),
            "low": float(bar.low),
            "close": bar_close,
            "volume": float(bar.volume),
            "source": "ibkr",
            "knowledge_time": kt.isoformat(),
            "raw_open": raw_open if raw_open != corrected_open else None,
        }

        staging_file = self.staging_path_for(bar_ts.to_pydatetime())
        staging_file.parent.mkdir(parents=True, exist_ok=True)

        if staging_file.exists():
            last_line = ""
            try:
                with open(staging_file, "rb") as f:
                    f.seek(0, 2)
                    pos = f.tell()
                    read_size = min(pos, 300)
                    f.seek(pos - read_size)
                    last_line = f.read().decode("utf-8", errors="replace").strip().rsplit("\n", 1)[-1]
            except OSError:
                pass
            if last_line:
                try:
                    if json.loads(last_line).get("timestamp", "") == ts_key:
                        return
                except (json.JSONDecodeError, ValueError):
                    pass

        with open(staging_file, "a") as f:
            f.write(json.dumps(bar_data) + "\n")

        self._bars_received += 1
        self._last_bar_time = kt
        self._update_heartbeat()

        if self._supervisor:
            self._supervisor.pulse_heartbeat()

    def _check_watchdog(self) -> None:
        if self._last_bar_time is None:
            if (
                self._subscribe_time is not None
                and is_forex_market_open()
                and (time.monotonic() - self._subscribe_time) > WATCHDOG_INITIAL_TIMEOUT_S
            ):
                self._attempt_resubscribe()
            return

        elapsed = (datetime.now(UTC) - self._last_bar_time).total_seconds()
        if elapsed > STALENESS_THRESHOLD_SECONDS and is_forex_market_open():
            self._attempt_resubscribe()

    def _attempt_resubscribe(self) -> None:
        if self._resubscribe.is_exhausted():
            self._state = "DEGRADED"
            self._subscribed = False
            self._update_heartbeat()
            return

        cont, backoff = self._resubscribe.register_attempt()
        if not cont:
            logger.error("resubscribe_exhausted pair=%s", self._pair)
            self._state = "DEGRADED"
            self._subscribed = False
            self._update_heartbeat()
            return

        if self._subscribe_time is not None and (time.monotonic() - self._subscribe_time) < backoff:
            return

        logger.warning(
            "resubscribe_attempt pair=%s attempt=%d backoff_s=%.0f",
            self._pair,
            self._resubscribe.attempts,
            backoff,
        )

        time.sleep(backoff)

        try:
            if self._bars_handle is not None:
                self._ib.cancelHistoricalData(self._bars_handle)
            self._subscribe()
        except Exception:
            logger.exception("resubscribe_failed pair=%s", self._pair)
            if self._resubscribe.is_exhausted():
                self._state = "DEGRADED"
                self._subscribed = False
                self._update_heartbeat()

    def _update_heartbeat(self) -> None:
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        status = self.get_status()
        status["pairs_active"] = [self._pair] if self._subscribed else []
        status["pairs_failed"] = (
            []
            if self._subscribed
            else ([self._pair] if self._state == "DEGRADED" else [])
        )
        payload = json.dumps(status, indent=2)

        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.heartbeat_path.parent),
            suffix=".tmp",
        )
        try:
            os.write(fd, payload.encode())
            os.close(fd)
            os.replace(tmp_path, str(self.heartbeat_path))
        except Exception:
            logger.exception("heartbeat_write_failed")
            try:
                os.close(fd)
            except OSError:
                pass

    def consolidate_day(self, date: datetime) -> int:
        return consolidate_day(self._pair, date, river_root=self._root)

    def consolidate_all_pending(self) -> int:
        return consolidate_all_pending(self._pair, river_root=self._root)


# Re-export constants for tests
__all__ = [
    "RiverStreamer",
    "CONSECUTIVE_GOOD_BARS_RESET",
    "RESUBSCRIBE_BACKOFF_S",
    "RESUBSCRIBE_MAX_ATTEMPTS",
]
