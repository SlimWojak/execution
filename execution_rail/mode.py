"""Operating mode — contract surface for broker factory dispatch.

Values mirror en1gma.console.governance.governance.OperatingMode (SW08).
This module stays peer-isolated: execution_rail does not import en1gma.
Callers pass mode at factory construction; en1gma maps its enum here
via value compatibility (both str Enums with identical members).
"""

from __future__ import annotations

from enum import Enum


class OperatingMode(str, Enum):
    TEST = "TEST"
    SHADOW = "SHADOW"
    PAPER = "PAPER"
    LIVE = "LIVE"
