"""run.py --list-grants CLI tests."""

from __future__ import annotations

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


def test_list_grants_empty_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "mode_grants.jsonl"
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(ledger))

    result = _run("--list-grants")

    assert result.returncode == 0
    assert "no grants recorded" in result.stdout


def test_list_grants_shows_record(tmp_path, monkeypatch):
    ledger = tmp_path / "mode_grants.jsonl"
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(ledger))

    grant = _run(
        "--grant-mode", "PAPER",
        "--reason", "list test",
        "--grantor", "opus",
        env={"EXECUTION_MODE_GRANTS_PATH": str(ledger)},
    )
    assert grant.returncode == 0

    result = _run("--list-grants", env={"EXECUTION_MODE_GRANTS_PATH": str(ledger)})

    assert result.returncode == 0
    assert "PAPER" in result.stdout
    assert "list test" in result.stdout


def test_list_grants_mode_filter_excludes_other_modes(tmp_path, monkeypatch):
    ledger = tmp_path / "mode_grants.jsonl"
    monkeypatch.setenv("EXECUTION_MODE_GRANTS_PATH", str(ledger))

    grant = _run(
        "--grant-mode", "PAPER",
        "--reason", "paper only",
        "--grantor", "opus",
        env={"EXECUTION_MODE_GRANTS_PATH": str(ledger)},
    )
    assert grant.returncode == 0

    result = _run(
        "--list-grants", "--mode", "SHADOW",
        env={"EXECUTION_MODE_GRANTS_PATH": str(ledger)},
    )

    assert result.returncode == 0
    assert "no grants recorded" in result.stdout
