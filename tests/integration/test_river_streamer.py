"""River integration tests (TR17-TR18) — env-gated."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def gateway_available():
    if os.environ.get("IBKR_INTEGRATION_TEST") != "1":
        pytest.skip("IBKR_INTEGRATION_TEST=1 required")


def test_tr17_live_streamer_smoke(gateway_available, tmp_path):
    """5 min run → ≥1 bar in staging, heartbeat connected+subscribed."""
    from execution_rail.river.streamer import RiverStreamer

    streamer = RiverStreamer(
        pair="EURUSD",
        river_root=tmp_path,
        ibkr_port=int(os.environ.get("IBKR_PORT", "4002")),
    )

    import threading

    t = threading.Thread(target=streamer.start, daemon=True)
    t.start()
    t.join(timeout=300)
    streamer.stop()

    staging = tmp_path / "EURUSD" / ".staging"
    jsonl_files = list(staging.glob("*.jsonl")) if staging.exists() else []
    assert jsonl_files, "expected staging JSONL after run"

    hb_path = tmp_path / ".heartbeat.json"
    assert hb_path.exists()
    import json

    hb = json.loads(hb_path.read_text())
    assert hb.get("connected") is True
    assert hb.get("subscribed") is True


def test_tr18_writer_fetch_day_immutable(gateway_available, tmp_path):
    from execution_rail.river.writer import RiverWriter

    writer = RiverWriter(river_root=tmp_path)
    day = datetime.now(UTC) - timedelta(days=2)
    df = writer.fetch_pair_day("EURUSD", day)
    if df is None or df.empty:
        pytest.skip("no bars returned from Gateway for test day")

    written = writer.write_day_if_absent("EURUSD", day, df)
    assert written > 0

    with pytest.raises(FileExistsError, match="INV-RIVER-IMMUTABLE"):
        writer.write_day_if_absent("EURUSD", day, df)
