"""IB Gateway reachability — operational check (TCP today, API in Brief 3)."""

from __future__ import annotations

import socket
from typing import Any

from . import config


def check_gateway_reachable(
    host: str | None = None,
    port: int | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """TCP port check — same surface as en1gma sentinel check_ibkr_gateway."""
    host = host or config.IB_GATEWAY_HOST
    port = port if port is not None else config.IB_GATEWAY_PORT_PAPER
    timeout_s = timeout_s if timeout_s is not None else config.IB_GATEWAY_TIMEOUT_S

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        sock.connect((host, port))
        sock.close()
        return {
            "name": "ibkr_gateway",
            "passed": True,
            "detail": f"port {port} reachable at {host}",
            "critical": True,
        }
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        return {
            "name": "ibkr_gateway",
            "passed": False,
            "detail": f"port {port} at {host}: {exc}",
            "critical": True,
        }
