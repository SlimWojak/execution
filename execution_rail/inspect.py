"""Passive runtime inspection surface for MCP and operator probes."""

from __future__ import annotations

from typing import Any

from .gateway import check_gateway_reachable


def _serialize(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def inspect_runtime(
    *,
    broker: Any = None,
    supervisor: Any = None,
    streamer: Any = None,
    include_gateway: bool = True,
) -> dict[str, Any]:
    """Return JSON-serializable state without owning runtime objects."""
    return {
        "broker": _serialize(broker.snapshot()) if broker else None,
        "supervisor": supervisor.get_status() if supervisor else None,
        "river_streamer": streamer.get_status() if streamer else None,
        "gateway_reachable": check_gateway_reachable() if include_gateway else None,
    }
