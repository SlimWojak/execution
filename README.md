# Execution Rail

Lean, isolated **broker + river** module — candidate_C **EXECUTION** slot.

Owns the full IBKR capital path end-to-end: live bar ingest, on-disk storage layout, broker connection, and trade execution. No en1gma import. Phoenix is read-only source reference.

**Version:** 0.4.0

---

## What this repo is

| In scope | Out of scope |
|----------|--------------|
| `BrokerAdapter` protocol + IB paper adapter | Strategy chain, governance, intent builder |
| IB Gateway connection + supervisor + halt escalation | en1gma orchestrators (`run_ars_session` wiring) |
| Live 1m bar streamer + historical writer + seam | Path rename `~/phoenix-river/` → `~/river/` |
| clientId allocation across Gateway multiplex | LIVE capital (T2-gated; paper only today) |

---

## Architecture

Two independent IB API surfaces share one Gateway. They are **not** coupled through a single wrapper.

```
┌─────────────────────────────────────────────────────────────────┐
│  IB Gateway  127.0.0.1:4002 (paper) / 4001 (live, T2-gated)    │
└────────────┬────────────────────────────────────┬───────────────┘
             │ clientId=1                         │ clientId=2
             ▼                                    ▼
┌────────────────────────┐            ┌──────────────────────────┐
│  execution_rail/river/ │            │  execution_rail/ib/      │
│  reqHistoricalData     │            │  placeOrder / positions  │
│  keepUpToDate → JSONL  │            │  IBPaperAdapter          │
└───────────┬────────────┘            └────────────┬─────────────┘
            │                                      │
            ▼                                      ▼
   ~/phoenix-river/                      OrderIntent → FillEvent
   {PAIR}/.staging/*.jsonl               (from en1gma, via factory)
   {PAIR}/YYYY/MM/DD.parquet
   .heartbeat.json
```

**Broker order path** (en1gma consumes, does not implement):

```
OrderIntent → governance.check() [en1gma]
           → build_broker(mode, halt) [broker_factory.py]
           → BrokerAdapter [broker_protocol.py]
           → IB Gateway
```

**River ingest path** (self-contained in this repo):

```
IB Gateway → RiverStreamer → staging JSONL → seam → immutable daily parquet
          → .heartbeat.json (read by en1gma LiveRiverReader)
```

---

## Design choices (read before changing anything)

### clientId allocation — `execution_rail/ib/client_id.py`

| Role | ID | Module |
|------|-----|--------|
| RIVER | 1 | `river/streamer.py` — live bars |
| BROKER | 2 | `ib/paper_adapter.py` — orders |
| COO | 3 | Constellation MCP inspect |
| DRILL | 99 | `river/writer.py`, manual drills |

Hardcoded clientId outside the allocator is a contract violation.

### `ib_insync` isolation — exactly 3 import sites

Broker and River use different IB API surfaces. Coupling them in one wrapper would conflate concerns.

| File | Domain |
|------|--------|
| `ib/real_client.py` | Orders, account, positions |
| `river/streamer.py` | Live `reqHistoricalData(keepUpToDate=True)` |
| `river/writer.py` | Historical backfill |

All imports are function-scoped (same pattern as `real_client.py`). Grep audit: `rg 'from ib_insync' execution_rail/` → 3 files.

### Three layers of resilience

| Layer | Owner | Handles |
|-------|-------|---------|
| 1 — IBC + launchd | `~/ibc/` | Gateway dead, login, daily IB restart |
| 2 — Supervisor | in-process | Gateway up but API connection silent |
| 3 — launchd KeepAlive | streamer plist | Process crash restart |

Broker uses `IBKRSupervisor` (5s heartbeat, 15s to DEAD). River uses `RiverSupervisor` (60s heartbeat, 3 min to DEAD, **market-hours gate** — weekend silence does not escalate).

### Halt policy

Supervisor heartbeat recovery does **not** auto-clear halt. Operator inspects, fixes root cause, clears manually. See `INV-HALT-OVERRIDES-ALL`.

### Mode promotion ledger

`PAPER` construction is gated by `execution_rail/mode_promotion.py`. A current grant in `~/execution/state/mode_grants.jsonl` is required before `build_broker(OperatingMode.PAPER, ...)` or `supervised_paper_session(...)` can create a real IB paper adapter. `LIVE` remains unavailable even if a grant is recorded.

### On-disk path

Data writes to `~/phoenix-river/` (name is historical; ownership is this repo). Override via `RIVER_ROOT` env var. 19+ en1gma consumers reference this path — rename is a separate migration brief.

### River invariants

| Invariant | Rule |
|-----------|------|
| `INV-RIVER-IMMUTABLE` | Daily parquet is write-once |
| `INV-NO-FORMING-CANDLE` | Streamer never emits incomplete bars |
| `INV-RIVER-BITEMPORAL` | Every bar has `timestamp` + `knowledge_time` |
| `INV-RIVER-MARKET-HOURS-ESCALATION` | River supervisor halts only during forex hours |

---

## Module map

```
execution/
├── run.py                          # --status, --protocol-check, --health
├── scripts/start_river_streamer.py # CLI daemon entry
├── drills/                         # manual Gateway validation
├── execution_rail/
│   ├── broker_protocol.py          # BrokerAdapter Protocol
│   ├── broker_factory.py           # build_broker() — sole construction site
│   ├── broker_adapter.py           # PaperBroker (TEST/SHADOW)
│   ├── halt_types.py               # LocalHaltSignal + HaltSignaler protocol
│   ├── inspect.py                  # passive runtime inspection surface
│   ├── mode_promotion.py           # PAPER promotion grant ledger
│   ├── ib/
│   │   ├── real_client.py          # sole broker ib_insync surface
│   │   ├── paper_adapter.py        # IBPaperAdapter (PAPER mode)
│   │   ├── client_id.py            # RIVER/BROKER/COO/DRILL allocator
│   │   ├── supervisor.py           # IBKRSupervisor + Watchdog
│   │   ├── heartbeat.py            # HeartbeatMonitor
│   │   ├── config.py               # ReconnectTracker
│   │   └── session.py              # supervised_paper_session()
│   └── river/
│       ├── schema.py               # CANONICAL_PAIRS, validators, get_river_root()
│       ├── streamer.py             # live 1m ingest → staging JSONL
│       ├── writer.py               # historical IB → daily parquet
│       ├── seam.py                 # staging JSONL → immutable parquet
│       ├── supervisor.py           # RiverSupervisor (market-hours gated)
│       ├── resubscribe.py          # RiverResubscribeTracker
│       └── synthetic.py            # deterministic test bars
├── docs/runbooks/
│   ├── IB_GATEWAY_OPERATIONS.md    # Layer 1 IBC activation
│   ├── RIVER_OPERATIONS.md         # streamer ops + seam
│   ├── ibc/                        # plist + keychain templates
│   └── river/                      # streamer plist template
└── tests/                          # unit + contract + integration (env-gated)
```

---

## Production activation

Execute in order on the prod machine. Each phase has a verification gate before proceeding.

### Phase 0 — Repo setup

```bash
git clone <repo> ~/execution && cd ~/execution
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python run.py --status
python run.py --health          # TCP on 127.0.0.1:4002 — fails until Gateway up
pytest                          # 70 pass, 5 skipped (no Gateway needed)
```

### Phase 1 — IB Gateway (Layer 1: IBC)

Gateway must be running before streamer or broker drills.

```bash
cp -r ~/ibc ~/ibc.bak.$(date +%Y-%m-%d)
security add-generic-password -a "$USER" -s ibkr_paper -w '<password>'
# Apply templates from docs/runbooks/ibc/ — replace paths for this machine
plutil -lint ~/ibc/local.ibc-gateway.plist
bash ~/ibc/stop.sh
launchctl load ~/ibc/local.ibc-gateway.plist
bash ~/ibc/check_gateway.sh     # GATE: Gateway reachable on :4002
```

Full detail: [`docs/runbooks/IB_GATEWAY_OPERATIONS.md`](docs/runbooks/IB_GATEWAY_OPERATIONS.md)

### Phase 2 — Broker validation

Confirms clientId=2 (BROKER) works on shared Gateway.

```bash
python - <<'PY'
from execution_rail.mode import OperatingMode
from execution_rail.mode_promotion import grant_mode
grant_mode(OperatingMode.PAPER, reason="broker validation", grantor="operator")
PY

python drills/ib_paper_validation.py
python drills/ib_paper_roundtrip.py    # GATE: BUY→SELL round-trip fills
IBKR_INTEGRATION_TEST=1 pytest tests/integration/test_ib_paper_roundtrip.py -m integration
```

### Phase 3 — River streamer (parallel cutover)

Run en1gma streamer **alongside** phoenix streamer first. Different clientIds — no collision. Both write same staging dir; dedup by timestamp prevents duplicates.

```bash
# Foreground — no supervisor for initial smoke
python scripts/start_river_streamer.py --pair EURUSD --port 4002 --no-supervisor

# Observe:
#   ~/phoenix-river/.heartbeat.json     → connected + subscribed
#   ~/phoenix-river/EURUSD/.staging/    → new JSONL lines arriving
```

**GATE:** ≥1 forex hour clean parallel run with phoenix still running. Sample bars match (timestamp + OHLC).

Then cut over:

```bash
# 1. Stop phoenix streamer manually
# 2. Install launchd unit:
mkdir -p ~/execution/logs/river
cp docs/runbooks/river/local.river-streamer.plist.template \
   ~/Library/LaunchAgents/com.a8ra.execution-river-streamer.plist
# Edit plist: replace __HOME__ with actual home path (e.g. /Users/<user>)
plutil -lint ~/Library/LaunchAgents/com.a8ra.execution-river-streamer.plist
launchctl load ~/Library/LaunchAgents/com.a8ra.execution-river-streamer.plist

# GATE: en1gma streamer solo ≥1 hour, bars continue, no halt
# GATE: re-run broker drill — BROKER=2 still works
```

Full detail: [`docs/runbooks/RIVER_OPERATIONS.md`](docs/runbooks/RIVER_OPERATIONS.md)

### Phase 4 — Integration tests (optional, Gateway required)

```bash
IBKR_INTEGRATION_TEST=1 pytest tests/integration/ -m integration
```

### Rollback

| Failure | Action |
|---------|--------|
| Streamer misbehaves | `launchctl unload` river plist; restart phoenix manually |
| Gateway misbehaves | restore `~/ibc` from backup; unload IBC plist |
| Code regression | revert commit; no data loss (both streamers write same dir) |

---

## Dev quick reference

```bash
source .venv/bin/activate
pytest                                    # unit + contract
IBKR_INTEGRATION_TEST=1 pytest tests/integration/ -m integration

# supervised broker session (Python)
from execution_rail.halt_types import LocalHaltSignal
from execution_rail.ib.session import supervised_paper_session
from execution_rail.mode import OperatingMode
from execution_rail.mode_promotion import grant_mode

grant_mode(OperatingMode.PAPER, reason="supervised session", grantor="operator")
halt = LocalHaltSignal()
with supervised_paper_session(halt, on_alert=print) as (adapter, sup, wd):
    ...

# candidate_C contract vocabulary
from execution_rail.broker_protocol import OrderIntent
fill = adapter.submit_intent(OrderIntent("EURUSD", "LONG", 20_000.0, 0.0))
snapshot = adapter.snapshot()

# historical backfill (clientId 99)
from execution_rail.river.writer import RiverWriter
RiverWriter().capture_all(lookback_days=7)

# forex-day seam (staging → parquet)
from execution_rail.river.seam import consolidate_all_pending
consolidate_all_pending("EURUSD")
```

---

## Brief chain

| # | Module | Status |
|---|--------|--------|
| 1 | BROKER_ADAPTER | ✓ Protocol + factory + PaperBroker |
| 2 | IB_PAPER_ADAPTER | ✓ Phoenix IB core lift, IBPaperAdapter |
| 3 | IB_CONNECTION_SUPERVISOR | ✓ Supervisor, heartbeat, clientId, IBC runbooks |
| 4 | RIVER_IBKR_STREAMER | ✓ Streamer, writer, schema, seam, RiverSupervisor |
| 5 | IBC_LIFECYCLE_SUPERVISOR | pending — wire `~/ibc/local.ibc-gateway.plist` |
| 6 | IB_LIVE_ADAPTER | pending — T2-gated live port |

---

## Cross-references

- Shape: `~/constellation/future_scope/candidate_C_integrated_mcp_body.md`
- Hedge: this rail is candidate-neutral infrastructure even while it occupies candidate_C's `execution_the_capital_path.rail` slot
- Source lift: `phoenix/river/`, `phoenix/drills/ibkr_paper_*.py`
- Consumer: en1gma reads `~/phoenix-river/` via `LiveRiverReader`; imports broker via thin wiring brief (not yet done)
- Secrets: never commit `.env` or Gateway passwords; keychain only
