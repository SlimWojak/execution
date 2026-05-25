"""Reserved IBKR API clientId allocations — INV-IBKR-CLIENT-ID-ALLOCATION."""

from __future__ import annotations

from enum import IntEnum


class ClientIdRole(IntEnum):
    """ib_insync multiplexes via clientId — collisions silently break."""

    RIVER = 1
    BROKER = 2
    COO = 3
    DRILL = 99


def allocate_client_id(role: ClientIdRole) -> int:
    return int(role)
