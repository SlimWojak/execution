"""Runtime inspection tests."""

from execution_rail.broker_adapter import PaperBroker
from execution_rail.halt_types import LocalHaltSignal
from execution_rail.inspect import inspect_runtime
from execution_rail.river.streamer import RiverStreamer


def test_inspect_runtime_serializes_passive_handles(tmp_path):
    broker = PaperBroker(LocalHaltSignal())
    broker.open_position("EURUSD", "LONG", 1.0, 1.1)
    streamer = RiverStreamer(pair="EURUSD", river_root=tmp_path)

    status = inspect_runtime(
        broker=broker,
        streamer=streamer,
        include_gateway=False,
    )

    assert status["broker"]["positions"]
    assert status["river_streamer"]["pair"] == "EURUSD"
    assert status["gateway_reachable"] is None
