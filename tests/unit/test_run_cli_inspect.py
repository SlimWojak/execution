"""run.py --inspect CLI tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from run import cmd_inspect


def test_inspect_gateway_up(capsys):
    reachable = {
        "name": "ibkr_gateway",
        "passed": True,
        "detail": "port 4002 reachable",
        "critical": True,
    }
    with patch("execution_rail.inspect.check_gateway_reachable", return_value=reachable):
        code = cmd_inspect()

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gateway_reachable"]["passed"] is True


def test_inspect_gateway_down(capsys):
    unreachable = {
        "name": "ibkr_gateway",
        "passed": False,
        "detail": "connection refused",
        "critical": True,
    }
    with patch("execution_rail.inspect.check_gateway_reachable", return_value=unreachable):
        code = cmd_inspect()

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["gateway_reachable"]["passed"] is False
