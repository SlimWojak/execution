"""Mode-promotion ledger — structural gate for real broker surfaces."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mode import OperatingMode

MODE_GRANTS_ENV = "EXECUTION_MODE_GRANTS_PATH"


class ModePromotionError(PermissionError):
    """Raised when a mode lacks a current grant."""


def grants_path() -> Path:
    return Path(
        os.environ.get(
            MODE_GRANTS_ENV,
            str(Path.home() / "execution" / "state" / "mode_grants.jsonl"),
        )
    )


def _normalize_mode(mode: OperatingMode | str) -> str:
    return mode.value if isinstance(mode, OperatingMode) else mode


def grant_mode(
    mode: OperatingMode | str,
    *,
    reason: str,
    grantor: str,
    path: Path | None = None,
) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "mode": _normalize_mode(mode),
        "reason": reason,
        "grantor": grantor,
    }
    target = path or grants_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def latest_grant(
    mode: OperatingMode | str,
    *,
    path: Path | None = None,
) -> dict[str, Any] | None:
    target = path or grants_path()
    if not target.exists():
        return None

    expected_mode = _normalize_mode(mode)
    latest: dict[str, Any] | None = None
    with open(target) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("mode") == expected_mode:
                latest = record
    return latest


def assert_mode_granted(mode: OperatingMode | str) -> dict[str, Any]:
    grant = latest_grant(mode)
    if grant is None:
        raise ModePromotionError(
            f"mode {_normalize_mode(mode)} requires a promotion grant"
        )
    return grant
