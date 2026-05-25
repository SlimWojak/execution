#!/usr/bin/env python3
"""Execution rail — capital path module (candidate_C)

BrokerAdapter protocol → PaperBroker → future IB adapters.

Usage:
    python run.py --protocol-check   # BrokerAdapter + factory smoke
    python run.py --health           # Gateway TCP reachability (paper port)
    python run.py --status           # Module readiness summary
    python run.py --grant-mode PAPER --reason "..." --grantor "..."
    python run.py --list-grants [--mode PAPER]
    python run.py --inspect          # JSON runtime snapshot (gateway probe)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class _NoHalt:
    def check(self) -> None:
        return None


def cmd_protocol_check() -> int:
    from execution_rail.broker_factory import build_broker
    from execution_rail.broker_protocol import BrokerAdapter
    from execution_rail.broker_adapter import PaperBroker
    from execution_rail.mode import OperatingMode

    halt = _NoHalt()
    broker = build_broker(OperatingMode.TEST, halt)

    checks = [
        ("isinstance PaperBroker", isinstance(broker, PaperBroker)),
        ("isinstance BrokerAdapter", isinstance(broker, BrokerAdapter)),
    ]

    order = broker.open_position("EURUSD", "LONG", 1.0, 1.1000)
    checks.append(("open_position", order.success))

    exit_ = broker.close_position(order.position_id or "", 1.1010)
    checks.append(("close_position", exit_.success))

    print("Protocol Check")
    print("=" * 40)
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        all_ok = all_ok and ok
    print()
    return 0 if all_ok else 1


def cmd_health() -> int:
    from execution_rail import config
    from execution_rail.gateway import check_gateway_reachable

    result = check_gateway_reachable()
    print("Health Check")
    print("=" * 40)
    print(f"  host: {config.IB_GATEWAY_HOST}")
    print(f"  paper_port: {config.IB_GATEWAY_PORT_PAPER}")
    print(f"  [{('PASS' if result['passed'] else 'FAIL')}] {result['name']}: {result['detail']}")
    print()
    return 0 if result["passed"] else 1


def cmd_status() -> None:
    from execution_rail import __version__
    from execution_rail import config

    print("Execution Rail Status")
    print("=" * 40)
    print(f"  version: {__version__}")
    print(f"  broker: PaperBroker (BrokerAdapter Protocol)")
    print(f"  ib_paper_adapter: landed (PAPER mode → real IB Gateway)")
    print(f"  ib_live_adapter:  pending (T2 ceremony)")
    print(f"  gateway: {config.IB_GATEWAY_HOST}:{config.IB_GATEWAY_PORT_PAPER} (paper)")
    print()


def cmd_grant_mode(mode: str, reason: str, grantor: str) -> int:
    from execution_rail.mode import OperatingMode
    from execution_rail.mode_promotion import grant_mode

    record = grant_mode(OperatingMode(mode), reason=reason, grantor=grantor)
    print(json.dumps(record, sort_keys=True))
    return 0


def cmd_list_grants(mode_filter: str | None) -> int:
    from execution_rail.mode_promotion import grants_path

    path = grants_path()
    if not path.exists():
        print("no grants recorded")
        return 0

    records: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if mode_filter and record.get("mode") != mode_filter:
                continue
            records.append(record)

    tail = records[-10:]
    if not tail:
        print("no grants recorded")
        return 0

    for record in tail:
        print(json.dumps(record, sort_keys=True))
    return 0


def cmd_inspect() -> int:
    from execution_rail.inspect import inspect_runtime

    status = inspect_runtime(include_gateway=True)
    print(json.dumps(status, sort_keys=True))
    gateway = status.get("gateway_reachable") or {}
    return 0 if gateway.get("passed") else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Execution rail — capital path module")
    parser.add_argument("--protocol-check", action="store_true", help="BrokerAdapter + factory smoke")
    parser.add_argument("--health", action="store_true", help="IB Gateway TCP reachability")
    parser.add_argument("--status", action="store_true", help="Module readiness summary")
    parser.add_argument("--drill-validation", action="store_true", help="Run IB paper validation drill")
    parser.add_argument("--drill-roundtrip", action="store_true", help="Run IB paper round-trip drill")
    parser.add_argument(
        "--grant-mode",
        choices=["SHADOW", "PAPER"],
        help="Record a mode promotion grant (requires --reason and --grantor)",
    )
    parser.add_argument("--reason", help="Grant reason (required with --grant-mode)")
    parser.add_argument("--grantor", help="Grantor identity (required with --grant-mode)")
    parser.add_argument("--list-grants", action="store_true", help="Show last 10 grants from JSONL ledger")
    parser.add_argument(
        "--mode",
        choices=["SHADOW", "PAPER"],
        help="Filter --list-grants by mode",
    )
    parser.add_argument("--inspect", action="store_true", help="Print JSON runtime snapshot (gateway probe)")
    args = parser.parse_args()

    if args.grant_mode:
        if not args.reason or not args.grantor:
            parser.error("--grant-mode requires --reason and --grantor")
        if not args.reason.strip() or not args.grantor.strip():
            parser.error("--reason and --grantor must be non-empty")
        sys.exit(cmd_grant_mode(args.grant_mode, args.reason, args.grantor))
    if args.list_grants:
        sys.exit(cmd_list_grants(args.mode))
    if args.inspect:
        sys.exit(cmd_inspect())
    if args.protocol_check:
        sys.exit(cmd_protocol_check())
    if args.health:
        sys.exit(cmd_health())
    if args.status:
        cmd_status()
        return
    if args.drill_validation:
        from drills.ib_paper_validation import main as drill_main
        sys.exit(0 if drill_main() else 1)
    if args.drill_roundtrip:
        from drills.ib_paper_roundtrip import main as drill_main
        sys.exit(0 if drill_main() else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
