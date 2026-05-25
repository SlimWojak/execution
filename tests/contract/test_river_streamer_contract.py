"""River streamer contract tests (TR14-TR16)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from execution_rail.ib.client_id import ClientIdRole, allocate_client_id
from execution_rail.river.schema import validate_raw_bars
from execution_rail.river.streamer import RiverStreamer
from execution_rail.river.synthetic import SyntheticRiver


def test_tr14_streamer_client_id_from_allocator():
    streamer = RiverStreamer(pair="EURUSD", river_root=Path("/tmp/river-test"))
    assert streamer._client_id == allocate_client_id(ClientIdRole.RIVER)
    assert streamer._client_id == 1


def test_tr15_mock_bar_update_validates():
    streamer = RiverStreamer(pair="EURUSD", river_root=Path("/tmp/river-test"))
    synth = SyntheticRiver(seed_prefix="contract")
    start = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)
    end = datetime(2026, 1, 6, 12, 5, tzinfo=UTC)
    df = synth.generate_raw_bars("EURUSD", start, end)
    assert validate_raw_bars(df) == []


def test_tr16_heartbeat_wire_compat_keys(tmp_path):
    streamer = RiverStreamer(pair="EURUSD", river_root=tmp_path)
    streamer._state = "STREAMING"
    streamer._connected = True
    streamer._subscribed = True
    streamer._last_bar_time = datetime.now(UTC)
    streamer._session_start = datetime.now(UTC)
    streamer._update_heartbeat()

    hb = json.loads((tmp_path / ".heartbeat.json").read_text())
    # Keys LiveRiverReader consumes
    assert "connected" in hb
    assert "subscribed" in hb
    assert "last_bar_time" in hb
    assert hb["connected"] is True
    assert hb["subscribed"] is True
    assert hb["last_bar_time"] is not None
