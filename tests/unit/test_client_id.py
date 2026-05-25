"""ClientId allocator tests (TS01-TS04)."""

from execution_rail.ib.client_id import ClientIdRole, allocate_client_id


def test_ts01_broker():
    assert allocate_client_id(ClientIdRole.BROKER) == 2


def test_ts02_river():
    assert allocate_client_id(ClientIdRole.RIVER) == 1


def test_ts03_coo():
    assert allocate_client_id(ClientIdRole.COO) == 3


def test_ts04_drill():
    assert allocate_client_id(ClientIdRole.DRILL) == 99
