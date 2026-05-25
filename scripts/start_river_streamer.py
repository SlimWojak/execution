#!/usr/bin/env python3
"""CLI entry — start River IBKR streamer daemon."""

from __future__ import annotations

import argparse
import logging
import sys

from execution_rail.halt_types import LocalHaltSignal
from execution_rail.river.schema import get_river_root
from execution_rail.river.streamer import IBKR_DEFAULT_PORT, RiverStreamer
from execution_rail.river.supervisor import RiverSupervisor


def notify_river_alert(kind: str, detail: str) -> None:
    logging.getLogger("river_streamer").warning("alert kind=%s detail=%s", kind, detail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="River Streamer — IBKR live 1m bars")
    parser.add_argument("--pair", default="EURUSD")
    parser.add_argument("--port", type=int, default=IBKR_DEFAULT_PORT)
    parser.add_argument("--no-supervisor", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("river_streamer")
    log.info("daemon_start pair=%s port=%d root=%s", args.pair, args.port, get_river_root())

    halt_signal = LocalHaltSignal()
    supervisor: RiverSupervisor | None = None
    if not args.no_supervisor:
        supervisor = RiverSupervisor(halt_signal=halt_signal, on_alert=notify_river_alert)
        supervisor.start()

    streamer = RiverStreamer(pair=args.pair, ibkr_port=args.port, supervisor=supervisor)
    try:
        streamer.start()
    finally:
        if supervisor:
            supervisor.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
