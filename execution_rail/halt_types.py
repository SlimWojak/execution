"""
Halt-protocol types — execution-side minimal surface of the halt signal.

INVARIANT: INV-GOV-HALT-BEFORE-ACTION
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class HaltChecker(Protocol):
    def check(self) -> None:
        """Raises HaltError on halt; returns None otherwise."""
        ...


class HaltError(Exception):
    """Raised when capital action blocked by halt signal."""


@runtime_checkable
class HaltSignaler(Protocol):
    """Escalation surface for supervisor → halt."""

    def signal_local(self, source: str, reason: str) -> None: ...


@dataclass
class LocalHaltSignal:
    """Test/production halt — satisfies HaltChecker + HaltSignaler."""

    _halted: bool = field(default=False, repr=False)
    _reason: str = field(default="", repr=False)
    last_source: str = field(default="", repr=False)

    def check(self) -> None:
        if self._halted:
            raise HaltError(self._reason or "halt active")

    def signal_local(self, source: str, reason: str) -> None:
        self._halted = True
        self.last_source = source
        self._reason = f"{source}:{reason}"

    def clear(self) -> None:
        self._halted = False
        self._reason = ""
        self.last_source = ""

    @property
    def is_halted(self) -> bool:
        return self._halted
