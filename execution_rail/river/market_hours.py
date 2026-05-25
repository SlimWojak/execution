"""Forex market hours — Sunday 17:00 NY → Friday 17:00 NY."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def is_forex_market_open(when: datetime | None = None) -> bool:
    """True when forex market is open (NY perspective)."""
    now_ny = (when or datetime.now(NY)).astimezone(NY)
    dow = now_ny.weekday()
    hour = now_ny.hour

    if dow == 5:
        return False
    if dow == 6 and hour < 17:
        return False
    if dow == 4 and hour >= 17:
        return False
    return True
