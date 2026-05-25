#!/usr/bin/env python3
"""
IB paper round-trip drill — CONNECT → BUY → FILL → SELL → CLOSE → DISCONNECT.

Usage:
    python drills/ib_paper_roundtrip.py

Requires IB Gateway on localhost:4002, IBKR_MODE=PAPER, DU* paper account.
Uses EURUSD 20,000 units (IB forex minimum).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

FOREX_LOT = 20_000.0


class _NoHalt:
    def check(self) -> None:
        return None


def _header(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _step(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'✓' if ok else '✗'} {name}: {detail}")


def main() -> bool:
    from execution_rail.ib.client_id import ClientIdRole, allocate_client_id
    from execution_rail.ib.config import IBKRConfig, IBKRMode
    from execution_rail.ib.paper_adapter import IBPaperAdapter

    print("\n" + "#" * 60)
    print("# EXECUTION RAIL — PAPER TRADE ROUND-TRIP")
    print("# Date:", datetime.now(UTC).isoformat())
    print("#" * 60)

    config = IBKRConfig.from_env()
    config.client_id = allocate_client_id(ClientIdRole.DRILL)
    if config.mode != IBKRMode.PAPER:
        print(f"  FATAL: IBKR_MODE must be PAPER, got {config.mode.value}")
        return False

    adapter = IBPaperAdapter(_NoHalt(), config)

    _header("STEP 1: OPEN LONG EURUSD")
    open_result = adapter.open_position("EURUSD", "LONG", FOREX_LOT, 0.0)
    _step("OPEN", open_result.success, f"fill={open_result.fill_price}")
    if not open_result.success or not open_result.position_id:
        adapter.disconnect()
        return False

    _header("STEP 2: CLOSE POSITION")
    close_result = adapter.close_position(
        open_result.position_id,
        open_result.fill_price or 0.0,
        reason="drill_exit",
    )
    _step("CLOSE", close_result.success, f"pnl={close_result.realized_pnl:.2f}")

    _header("STEP 3: DISCONNECT")
    adapter.disconnect()
    _step("DISCONNECT", True, "Clean disconnect")

    ok = open_result.success and close_result.success and (open_result.fill_price or 0) > 0
    if ok:
        print("\n  PAPER TRADE ROUND-TRIP: PASS ✓")
    else:
        print("\n  PAPER TRADE ROUND-TRIP: INCOMPLETE")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
