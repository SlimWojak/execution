"""Unit tests for position lifecycle — lifted from en1gma."""

import pytest

from execution_rail.position import InvalidTransitionError, Position, PositionState


def test_position_lifecycle_long():
    pos = Position(
        position_id="POS-001", symbol="EURUSD",
        direction="LONG", size=1.0,
    )
    assert pos.state == PositionState.PENDING
    pos.fill(1.10000, 1.0)
    assert pos.state == PositionState.OPEN
    pos.close(1.10100)
    assert pos.state == PositionState.CLOSED
    assert pos.realized_pnl > 0


def test_position_lifecycle_short():
    pos = Position(
        position_id="POS-002", symbol="EURUSD",
        direction="SHORT", size=1.0,
    )
    pos.fill(1.10100, 1.0)
    pos.close(1.10000)
    assert pos.realized_pnl > 0


def test_position_halt():
    pos = Position(
        position_id="POS-003", symbol="EURUSD",
        direction="LONG", size=1.0,
    )
    pos.fill(1.10000, 1.0)
    pos.halt("HALT-001")
    assert pos.state == PositionState.HALTED


def test_invalid_transition():
    pos = Position(
        position_id="POS-004", symbol="EURUSD",
        direction="LONG", size=1.0,
    )
    pos.fill(1.10000, 1.0)
    pos.close(1.10100)
    with pytest.raises(InvalidTransitionError):
        pos.close(1.10200)
