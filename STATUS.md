# Execution Rail — STATUS

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Brief 1 | BROKER_ADAPTER — Protocol + factory scaffolded here (not in en1gma) |
| Brief 2 | IB_PAPER_ADAPTER — pending (lift phoenix drills) |
| Broker | PaperBroker only |
| IB wired | No |
| Tests | `pytest` in tests/ |

## Lifted from en1gma (2026-05-25)

- `broker_adapter.py` → `execution_rail/broker_adapter.py`
- `position.py` → `execution_rail/position.py`
- `halt_types.py` → `execution_rail/halt_types.py`

## Added (Brief 1 shape)

- `broker_protocol.py` — BrokerAdapter Protocol + OrderResult/ExitResult
- `broker_factory.py` — `build_broker(mode, halt)`
- `mode.py` — OperatingMode (SW08-compatible, peer-isolated)
- `gateway.py` — TCP reachability (Brief 3 upgrades to API round-trip)

## en1gma integration

**Not wired yet.** When ready, en1gma orchestrators import:

```python
from execution_rail.broker_factory import build_broker
from execution_rail.broker_protocol import BrokerAdapter, OrderResult
from execution_rail.mode import OperatingMode  # or map from en1gma governance enum
```

Zero changes to en1gma until that wiring brief lands.
