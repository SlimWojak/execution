"""
Halt-protocol types — execution-side minimal surface of the halt signal.

Lifted from: en1gma/console/execution/halt_types.py (SW33 peer doctrine)

execution_rail depends on a BEHAVIOR (HaltChecker), not a concrete
governance type. Orchestrators supply HaltSignal (or test fakes) at
construction time; duck typing satisfies the Protocol.

INVARIANT: INV-GOV-HALT-BEFORE-ACTION
"""

from __future__ import annotations

from typing import Protocol


class HaltChecker(Protocol):
    """Minimal halt-check surface consumed by the execution layer."""

    def check(self) -> None:
        """Raises HaltError on halt; returns None otherwise."""
        ...


class HaltError(Exception):
    """Raised when capital action blocked by halt signal."""
