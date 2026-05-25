# Execution Rail / EXECUTION

Lean, isolated capital path module — candidate_C **EXECUTION** slot.
Mirrors the RiverWriter pattern: one clean home, thin surface, no kernel bloat.

```
OrderIntent (from en1gma strategy chain)
    ↓
governance.check()          ← stays in en1gma (not duplicated here)
    ↓
build_broker(mode, halt)    ← sole construction site (broker_factory.py)
    ↓
BrokerAdapter Protocol      ← broker_protocol.py
    ├── PaperBroker         ← today (broker_adapter.py)
    ├── IBPaperAdapter      ← Brief 2 (lift phoenix drills)
    └── IBLiveAdapter       ← T2-gated ceremony
    ↓
IB Gateway (127.0.0.1:4002 paper / 4001 live)
```

## Scope discipline

| Layer | Module | Role |
|-------|--------|------|
| Contract | `broker_protocol.py` | BrokerAdapter Protocol + result types |
| Factory | `broker_factory.py` | `build_broker(mode, halt)` — sole construction |
| Paper | `broker_adapter.py` | Immediate-fill PaperBroker |
| Lifecycle | `position.py` | 5-state FSM + P&L |
| Halt peer | `halt_types.py` | HaltChecker Protocol (no en1gma import) |
| Mode | `mode.py` | OperatingMode enum (SW08-compatible values) |
| Gateway ops | `gateway.py` | TCP reachability (API round-trip in Brief 3) |
| Config | `config.py` | Host/port env overrides |

**Stays in en1gma:** `intent_builder.py`, governance, orchestrators, strategy chain.
**Lifted here:** everything that touches capital execution.

## Quick start

```bash
cd ~/execution
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python run.py --status
python run.py --protocol-check
python run.py --health          # TCP check on IB Gateway paper port
pytest
```

## Brief chain

1. **BROKER_ADAPTER** (this repo) — Protocol + factory + PaperBroker lift
2. **IB_PAPER_ADAPTER** — lift `phoenix/drills/ibkr_paper_*.py`, add `ib_insync`
3. **SENTINEL_LIVENESS_UPGRADE** — TCP → API round-trip
4. **IBC_LIFECYCLE_SUPERVISOR** — wire `~/ibc/local.ibc-gateway.plist`
5. **IB_LIVE_ADAPTER** — T2-gated live port

## Layout

```
execution/
├── run.py
├── pyproject.toml
├── execution_rail/
│   ├── broker_protocol.py
│   ├── broker_factory.py
│   ├── broker_adapter.py
│   ├── position.py
│   ├── halt_types.py
│   ├── mode.py
│   ├── gateway.py
│   └── config.py
├── tests/unit/
│   ├── test_broker_protocol.py
│   └── test_position.py
└── docs/
    └── BRIEF.MODULE.BROKER_ADAPTER.md
```

## Cross-reference

- Implements **EXECUTION** slot from `~/constellation/future_scope/candidate_C_integrated_mcp_body.md`
- Constellation MCP `ib` adapter wires here post-ATOM lock
- Source lift: `en1gma/console/execution/` + `phoenix/drills/ibkr_paper_*.py`

## Git

No secrets (`.env` gitignored). Tools + tests + STATUS in git.
