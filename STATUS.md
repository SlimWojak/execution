# Execution Rail — STATUS

| Field | Value |
|---|---|
| Version | 0.4.0 |
| Brief 1 | BROKER_ADAPTER ✓ |
| Brief 2 | IB_PAPER_ADAPTER ✓ |
| Brief 3 | IB_CONNECTION_SUPERVISOR ✓ |
| Brief 4 | RIVER_IBKR_STREAMER ✓ |
| Brief 5 | IBC_LIFECYCLE_SUPERVISOR — pending |
| Brief 6 | IB_LIVE_ADAPTER — pending (T2-gated) |

## Broker chain (self-contained)

Ingest, storage layout, broker connection, and trade execution all live in this repo. en1gma consumes `~/phoenix-river/` read-side only; phoenix is source reference.

The public broker surface now uses candidate_C contract nouns: `OrderIntent`, `FillEvent`, `CloseFillEvent`, and `PositionSnapshot`. Legacy `OrderResult` / `ExitResult` names remain aliases during consumer migration.

`PAPER` construction through the factory or `supervised_paper_session()` requires a mode-promotion grant in `~/execution/state/mode_grants.jsonl`. `LIVE` remains T2-gated and unimplemented.

## Three-layer resilience

| Layer | Owner | Handles |
|-------|-------|---------|
| 1 — IBC + launchd | `~/ibc/` | Gateway dead, login, daily IB restart |
| 2 — Supervisor | `execution_rail/ib/` + `execution_rail/river/` | Gateway up but API silent |
| 3 — launchd KeepAlive | river streamer plist | Streamer process crash restart |

## Module inventory

### Brief 3 — `execution_rail/ib/`

- `client_id.py` — RIVER=1, BROKER=2, COO=3, DRILL=99
- `heartbeat.py` — HeartbeatMonitor (INV-IBKR-FLAKEY-1)
- `supervisor.py` — IBKRSupervisor + Watchdog
- `config.py` — ReconnectTracker
- `session.py` — `supervised_paper_session()`
- `mode_promotion.py` — PAPER grant ledger
- `inspect.py` — passive runtime status aggregation

### Brief 4 — `execution_rail/river/`

- `schema.py` — CANONICAL_PAIRS, validators, `get_river_root()`
- `streamer.py` — live 1m ingest → staging JSONL (clientId 1)
- `writer.py` — historical backfill → daily parquet (clientId 99)
- `seam.py` — staging → immutable parquet
- `supervisor.py` — RiverSupervisor (market-hours gated)
- `resubscribe.py` — RiverResubscribeTracker
- `synthetic.py` — deterministic test bars
- `scripts/start_river_streamer.py` — CLI entry

## Tests

70 unit/contract pass + 5 integration skipped (env-gated)

```bash
pytest
IBKR_INTEGRATION_TEST=1 pytest tests/integration/ -m integration
```

## Production activation

See **README.md → Production activation** (Phases 0–4).

Runbooks:
- `docs/runbooks/IB_GATEWAY_OPERATIONS.md` — Layer 1 IBC
- `docs/runbooks/RIVER_OPERATIONS.md` — streamer cutover + seam
