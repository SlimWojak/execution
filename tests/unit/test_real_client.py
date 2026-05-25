"""RealIBKRClient unit tests."""

from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.real_client import RealIBKRClient


def test_intentional_disconnect_does_not_fire_callback():
    calls = {"n": 0}
    client = RealIBKRClient(
        IBKRConfig(mode=IBKRMode.MOCK),
        on_disconnect=lambda: calls.update(n=calls["n"] + 1),
    )

    client._intentional_disconnect = True
    client._handle_disconnect()

    assert calls["n"] == 0
