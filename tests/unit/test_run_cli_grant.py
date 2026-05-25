"""run.py --grant-mode CLI tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    import os

    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, "run.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=run_env,
    )


def test_grant_mode_paper_writes_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "mode_grants.jsonl"
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(ledger))

    result = _run(
        "--grant-mode", "PAPER",
        "--reason", "cli test",
        "--grantor", "opus",
    )

    assert result.returncode == 0
    assert "PAPER" in result.stdout
    record = json.loads(result.stdout.strip())
    assert record["mode"] == "PAPER"
    assert record["reason"] == "cli test"
    assert record["grantor"] == "opus"
    assert ledger.exists()


def test_grant_mode_live_rejected():
    result = _run(
        "--grant-mode", "LIVE",
        "--reason", "nope",
        "--grantor", "opus",
    )

    assert result.returncode != 0


def test_grant_mode_missing_reason_rejected():
    result = _run("--grant-mode", "PAPER", "--grantor", "opus")

    assert result.returncode != 0
