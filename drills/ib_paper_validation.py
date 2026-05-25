#!/usr/bin/env python3
"""
IB paper validation drill — adapted from phoenix S33.

Usage:
    python drills/ib_paper_validation.py

Requires IB Gateway on localhost:4002 and IBKR_MODE=PAPER in .env
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


def _header(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _result(name: str, passed: bool, details: str = "") -> None:
    print(f"  {'✓ PASS' if passed else '✗ FAIL'}: {name}")
    if details:
        print(f"         {details}")


def validate_guards() -> bool:
    _header("TEST 1: GUARD VALIDATION")
    from execution_rail.ib.client_id import ClientIdRole, allocate_client_id
    from execution_rail.ib.config import IBKRConfig, IBKRMode

    config = IBKRConfig.from_env()
    config.client_id = allocate_client_id(ClientIdRole.DRILL)
    if config.mode != IBKRMode.PAPER:
        _result("Mode detection", False, f"Expected PAPER, got {config.mode.value}")
        return False
    _result("Mode detection", True, f"Mode: {config.mode.value}")

    live_cfg = IBKRConfig(mode=IBKRMode.LIVE, allow_live=False)
    valid, errors = live_cfg.validate_startup()
    if not valid and any("INV-IBKR-PAPER-GUARD-1" in e for e in errors):
        _result("Live mode blocked", True, "INV-IBKR-PAPER-GUARD-1 enforced")
    else:
        _result("Live mode blocked", False, "Guard NOT enforced")
        return False

    ok, _ = config.validate_account("DU1234567")
    _result("Paper account validation", ok, "DU* prefix accepted")
    bad, _ = config.validate_account("U9999999")
    _result("Live account rejected", not bad, "U* prefix rejected in PAPER mode")
    return ok and not bad


def test_connection() -> tuple[bool, object | None]:
    _header("TEST 2: IBKR CONNECTION")
    from execution_rail.ib.client_id import ClientIdRole, allocate_client_id
    from execution_rail.ib.config import IBKRConfig
    from execution_rail.ib.real_client import RealIBKRClient

    config = IBKRConfig.from_env()
    config.client_id = allocate_client_id(ClientIdRole.DRILL)
    print(f"  Config: host={config.host}, port={config.port}, mode={config.mode.value}")
    client = RealIBKRClient(config)
    try:
        if client.connect():
            _result("Connection", True, f"Account: {client.account_id}")
            return True, client
    except Exception as exc:
        _result("Connection", False, str(exc))
        print("\n  HINT: Is IB Gateway running on localhost:4002?")
    return False, None


def test_account(client) -> bool:
    _header("TEST 3: ACCOUNT QUERY")
    account = client.get_account()
    if account and account.account_id:
        _result("Account query", True, f"Account: {account.account_id}")
        print(f"         Net Liquidation: ${account.net_liquidation:,.2f}")
        return True
    _result("Account query", False, "No account data")
    return False


def test_positions(client) -> bool:
    _header("TEST 4: POSITION QUERY")
    snapshot = client.get_positions()
    _result("Positions query", True, f"Found {len(snapshot.positions)} positions")
    for pos in snapshot.positions:
        print(f"         {pos.symbol}: {pos.quantity:,.0f} @ ${pos.avg_cost:.5f}")
    return True


def test_protocol_surface() -> bool:
    _header("TEST 5: BROKERADAPTER SURFACE")
    from execution_rail.broker_protocol import BrokerAdapter
    from execution_rail.ib.client_id import ClientIdRole, allocate_client_id
    from execution_rail.ib.config import IBKRConfig, IBKRMode
    from execution_rail.ib.paper_adapter import IBPaperAdapter

    class _NoHalt:
        def check(self) -> None:
            return None

    config = IBKRConfig.from_env()
    config.client_id = allocate_client_id(ClientIdRole.DRILL)
    if config.mode != IBKRMode.PAPER:
        _result("Protocol isinstance", False, "Requires PAPER config")
        return False

    adapter = IBPaperAdapter(_NoHalt(), config)
    ok = isinstance(adapter, BrokerAdapter)
    _result("Protocol isinstance", ok, "IBPaperAdapter satisfies BrokerAdapter")
    return ok


def main() -> bool:
    print("\n" + "#" * 60)
    print("# EXECUTION RAIL — IB PAPER VALIDATION")
    print("# Date:", datetime.now(UTC).isoformat())
    print("#" * 60)

    results: dict[str, bool] = {}
    results["guards"] = validate_guards()

    connected, client = test_connection()
    results["connection"] = connected
    if not connected or client is None:
        print("\n# VALIDATION INCOMPLETE: Connection failed")
        return False

    results["account"] = test_account(client)
    results["positions"] = test_positions(client)
    results["protocol"] = test_protocol_surface()

    _header("CLEANUP")
    client.disconnect()
    print("  Disconnected from IBKR")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  Tests: {passed}/{total} passed")
    for name, ok in results.items():
        print(f"  {'✓' if ok else '✗'} {name}")

    if passed == total:
        print("\n  IBKR PAPER VALIDATION: PASS ✓")
        return True
    print("\n  IBKR PAPER VALIDATION: INCOMPLETE")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
