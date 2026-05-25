"""
Synthetic River — deterministic bar generator for tests.

Invariants:
    INV-SYNTH-DETERMINISM: Same inputs → same outputs (seeded RNG)
    INV-SYNTH-SCHEMA: Output matches real River schema
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from .schema import CANONICAL_PAIRS, compute_bar_hashes

BASE_PRICES = {
    "EURUSD": 1.0850,
    "GBPUSD": 1.2650,
    "USDJPY": 148.50,
    "USDCHF": 0.9200,
    "AUDUSD": 0.6550,
    "USDCAD": 1.3550,
}


@dataclass
class SyntheticBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class SyntheticRiver:
    """Deterministic mock bar generator for offline tests."""

    def __init__(self, volatility: float = 0.0010, seed_prefix: str = "execution"):
        self.volatility = volatility
        self.seed_prefix = seed_prefix

    def generate_raw_bars(
        self,
        pair: str,
        start: datetime,
        end: datetime,
        *,
        interval_minutes: int = 1,
        source: str = "ibkr",
    ) -> pd.DataFrame:
        """Generate schema-valid RAW_BAR rows between start and end."""
        if pair not in CANONICAL_PAIRS:
            raise ValueError(f"Unsupported pair: {pair}")

        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        bars = self._generate_bars(pair, start, end, interval_minutes)
        if not bars:
            return pd.DataFrame(columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "source", "knowledge_time", "bar_hash",
            ])

        df = pd.DataFrame([b.to_dict() for b in bars])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["source"] = source
        df["knowledge_time"] = df["timestamp"] + pd.Timedelta(seconds=1)
        df["bar_hash"] = compute_bar_hashes(df)
        return df.sort_values("timestamp").reset_index(drop=True)

    def _generate_bars(
        self,
        pair: str,
        start: datetime,
        end: datetime,
        interval_minutes: int,
    ) -> list[SyntheticBar]:
        seed_data = (
            f"{self.seed_prefix}_{pair}_{interval_minutes}_"
            f"{start.isoformat()}_{end.isoformat()}"
        )
        seed = int(hashlib.sha256(seed_data.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        interval = timedelta(minutes=interval_minutes)
        price = BASE_PRICES.get(pair, 1.0)
        bars: list[SyntheticBar] = []
        current = start

        while current < end:
            change = rng.gauss(0, self.volatility)
            price = max(price * 0.5, price + change)
            high_offset = abs(rng.gauss(0, self.volatility * 0.5))
            low_offset = abs(rng.gauss(0, self.volatility * 0.5))
            close_offset = rng.gauss(0, self.volatility * 0.3)

            bars.append(
                SyntheticBar(
                    timestamp=current,
                    open=round(price, 5),
                    high=round(price + high_offset, 5),
                    low=round(price - low_offset, 5),
                    close=round(price + close_offset, 5),
                    volume=float(rng.randint(100, 10000)),
                )
            )
            current += interval

        return bars
