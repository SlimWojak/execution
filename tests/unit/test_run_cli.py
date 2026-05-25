"""run.py CLI surface tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_run_status_cli():
    result = subprocess.run(
        [sys.executable, "run.py", "--status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Execution Rail Status" in result.stdout
