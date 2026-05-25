"""Execution rail configuration — env overrides, no secrets in repo."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"

# IB Gateway defaults (paper). Brief 2 wires ib_insync against these.
IB_GATEWAY_HOST = os.environ.get("IB_GATEWAY_HOST", "127.0.0.1")
IB_GATEWAY_PORT_PAPER = int(os.environ.get("IB_GATEWAY_PORT_PAPER", "4002"))
IB_GATEWAY_PORT_LIVE = int(os.environ.get("IB_GATEWAY_PORT_LIVE", "4001"))
IB_GATEWAY_TIMEOUT_S = float(os.environ.get("IB_GATEWAY_TIMEOUT_S", "2"))
