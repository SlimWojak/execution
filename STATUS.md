# Execution Rail — STATUS

| Field | Value |
|---|---|
| Version | 0.3.0 |
| Brief 1 | BROKER_ADAPTER ✓ |
| Brief 2 | IB_PAPER_ADAPTER ✓ |
| Brief 3 | IB_CONNECTION_SUPERVISOR ✓ |
| Brief 4 prep | `docs/BRIEF.MODULE.RIVER_IBKR_STREAMER.PREP.md` |

## Two-layer IB resilience

| Layer | Module | Role |
|-------|--------|------|
| 1 — IBC | `~/ibc/` + runbook templates | Gateway process lifecycle (launchd) |
| 2 — Supervisor | `execution_rail/ib/supervisor.py` | In-session heartbeat → halt escalation |

## New in Brief 3

- `client_id.py` — RIVER=1, BROKER=2, COO=3, DRILL=99
- `heartbeat.py` — HeartbeatMonitor (INV-IBKR-FLAKEY-1)
- `supervisor.py` — IBKRSupervisor + Watchdog
- `config.py` — ReconnectTracker runtime
- `session.py` — `supervised_paper_session()` context manager
- `docs/runbooks/` — IBC activation + plist/keychain templates

## Tests

39 unit/contract pass + 3 integration skipped (env-gated)

## Manual activation (Layer 1)

See `docs/runbooks/IB_GATEWAY_OPERATIONS.md`
