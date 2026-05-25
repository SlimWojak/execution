# BRIEF.MODULE.RIVER_IBKR_STREAMER

> **Implementation note:** Shipped in `~/execution` at `execution_rail/river/` (v0.4.0). Brief originally targeted en1gma paths; adapted to candidate_C EXECUTION slot per Brief 1–3 pattern. On-disk path `~/phoenix-river/` unchanged.

| | |
|---|---|
| **Mission** | RIVER_OWNS_ITS_OWN_IB_INGEST |
| **Owner** | Opus (Cursor / factory) |
| **Format** | DENSE |
| **Date** | 2026-05-25 |
| **Series** | `BRIEF.MODULE.*` — fourth brief in module-by-module sweep |
| **Scope** | Lift phoenix-river's IB streaming + writing + schema + seam into en1gma. Replace dependency on out-of-repo phoenix-river daemon with a self-contained en1gma River streamer that uses the clientId allocator (RIVER=1) and supervisor pattern from brief 3. **KEEP** the on-disk data path (`~/phoenix-river/`) — name is historical, ownership is en1gma's. |

---

## Mission Statement

Today the en1gma kernel READS bars from `~/phoenix-river/{PAIR}/` — daily parquet + `.staging/*.jsonl` + `.heartbeat.json` — but the WRITER is phoenix's streamer process, running outside the en1gma repo and outside the brief chain.

This brief brings ingest ownership into en1gma. Lift `phoenix/river/` (2,628L across 9 files) into `en1gma/data/river/`, keeping the lean proven core (streamer + writer + schema + seam + synthetic + reader helpers) and dropping what en1gma doesn't need (`nex_ingestor.py` — one-time historical migration already complete; `ghost_policy.py` deferred). Replace phoenix streamer's random clientId (700-799) with `allocate_client_id(ClientIdRole.RIVER) = 1` (brief 3). Wire a `RiverSupervisor` with River-tuned thresholds (longer gaps are normal during off-hours) and the same halt-escalation pattern as the broker supervisor — `INV-IB-TWO-LAYER-RESILIENCE` applied to River.

The on-disk data path stays `~/phoenix-river/` for this brief. **19+ en1gma files reference that path directly**; a rename is a separate brief with its own migration story. `~/phoenix-river/` becomes a HISTORICAL NAME for a path en1gma now owns end-to-end.

**After this brief: the broker chain is self-contained.** en1gma owns data ingest, data storage layout, broker connection, and trade execution. Phoenix becomes pure source-repo reference.

---

## Context

**Status in:** expected — clean on main, post-MODULE.IB_CONNECTION_SUPERVISOR (724 unit/contract + integration env-gated)

**Sequencing.** Fourth in the module sweep because:
1. consumes brief 3's clientId allocator (RIVER=1) — the allocator invariant becomes meaningful only when a second consumer exists
2. reuses brief 3's supervisor pattern — proves it's reusable, not broker-specific
3. closes G's stated focus area: "the full river pipeline (including broker connection) optimised"
4. en1gma becomes self-contained — no out-of-repo daemon dependencies for the broker-trading chain

**Out of scope:**
- Rename `~/phoenix-river/` data path (separate brief — data-migration story; 19+ consumer references)
- `MODULE.GHOST_POLICY` (phoenix `ghost_policy.py` 104L — latent feature, not blocking)
- `MODULE.RIVER_NEX_INGESTOR` (one-time migration, archived)
- `MODULE.RIVER_MULTI_PAIR` (EUR/USD focus; multi-pair is a followup)
- `MODULE.RIVER_BACKFILL_AUTOMATION` (currently manual via writer; followup)
- `MODULE.SENTINEL_LIVENESS_UPGRADE` (independent track)

---

## Sprawl Audit

### Phoenix river surface — `/Users/a8ra_m3/phoenix/river/` — 2,628 lines total, PROVEN

| File | Lines | Role | Verdict |
|---|---|---|---|
| `streamer.py` | 718 | RiverStreamer — live 1m bar ingest via `reqHistoricalData(keepUpToDate=True)`. Dedup, staging JSONL writes, heartbeat, gap detection, continuity correction, resubscribe-with-backoff, watchdog, IB error callbacks. | **LIFT (T4).** Random clientId 700-799 → `allocate_client_id(ClientIdRole.RIVER)`. structlog → stdlib. Resubscribe extracted to `RiverResubscribeTracker` (T6). |
| `schema.py` | 142 | `CANONICAL_PAIRS` (6 pairs), `RAW_BAR_SCHEMA` (9 cols), `compute_bar_hashes`, `validate_raw_bars`, `get_river_root` (env override), `VALID_SOURCES`, `NEX_SOURCE_BOUNDARY=2025-11-22`. | **LIFT (T1).** Foundation. Pure pandas + pyarrow. en1gma promotes phoenix docstring invariants to first-class. |
| `writer.py` | 339 | Historical IB → daily parquet. `INV-RIVER-IMMUTABLE` (write-once). | **LIFT (T3).** structlog → stdlib. Random clientId → `allocate_client_id(ClientIdRole.DRILL=99)` (manual script). ib_insync gated import. |
| `seam.py` | 349 | Forex-day-close consolidation. At 17:00 NY, staging JSONL → immutable daily parquet. | **LIFT (T5).** Critical for write-once invariant. Idempotent re-run safe. |
| `synthetic_river.py` | 285 | Deterministic 1m bar generator for tests. | **LIFT (T2).** Land early so T8 tests can use it. |
| `reader.py` | 462 | Read-side parquet utilities. | **DO NOT LIFT WHOLESALE.** en1gma `data/river.py` already has the read surface. Cherry-pick missing utilities if discovered. Phoenix reader stays archived. |
| `nex_ingestor.py` | 190 | One-time NEX-parquet → River-parquet migration (boundary 2025-11-22). | **DO NOT LIFT.** Complete; archived. |
| `ghost_policy.py` | 104 | Gap-fill policy (ghost markers). | **DEFER** → `MODULE.GHOST_POLICY` followup. Not blocking. |
| `__init__.py` | 39 | Package exports. | Rewrite for en1gma. |

### en1gma existing surface

| File | Status |
|---|---|
| `en1gma/data/river.py` (~275L) | **UNCHANGED in primary path.** Consumer interface stays. We add the PRODUCER alongside, both pointing at `~/phoenix-river/`. May relocate as `en1gma/data/river/reader.py` with backwards-compat shim (Opus discretion). |
| 19 en1gma files referencing `~/phoenix-river/` | **UNCHANGED.** Path stays. `schema.get_river_root()` respects `RIVER_ROOT` env var → future rename can env-flip first. |
| `en1gma/scripts/sentinel.py` | **UNCHANGED.** Heartbeat wire format preserved. |

### `ib_insync` isolation evolution

| Pre-brief | Post-brief |
|---|---|
| 1 import file: `execution/ib/real_client.py` | 3 import files: `execution/ib/real_client.py` (broker — placeOrder), `data/river/streamer.py` (River live — reqHistoricalData keepUpToDate), `data/river/writer.py` (River backfill — reqHistoricalData one-shot) |

**`INV-IBKR-CLIENT-ISOLATION` updated** to permit exactly 3 import sites, each in its bounded domain. Broker and River use DIFFERENT IB API surfaces; coupling them through one wrapper would conflate unrelated concerns. Anything outside these 3 = contract violation (G3 grep gate).

### Bloat pruned

- `nex_ingestor.py` (190L) — complete migration
- `ghost_policy.py` (104L) — deferred
- `reader.py` (462L) — only cherry-pick missing utilities
- `structlog` dependency replaced with stdlib logging
- Random clientId 700-799 → allocator

**Net: ~756 lines + 1 dependency not lifted.**

---

## Target Shape

### Directory layout

```
en1gma/data/
├── __init__.py
├── bar_types.py              (unchanged)
├── tf_aggregator.py          (unchanged)
├── river.py                  (EVOLVED — backwards-compat shim re-exports)
└── river/                    (NEW SUBPACKAGE)
    ├── __init__.py
    ├── schema.py             (lifted)
    ├── synthetic.py          (lifted from synthetic_river.py)
    ├── writer.py             (lifted — historical backfill)
    ├── streamer.py           (lifted — live engine)
    ├── seam.py               (lifted — staging→parquet consolidation)
    ├── reader.py             (relocated LiveRiverReader + parquet helpers)
    ├── resubscribe.py        (NEW — RiverResubscribeTracker)
    └── supervisor.py         (NEW — RiverSupervisor; thin wrapper over brief-3 IBKRSupervisor)

en1gma/scripts/
└── start_river_streamer.py   (NEW — CLI entry)

en1gma/launchd/
└── local.river-streamer.plist (NEW)

en1gma/docs/runbooks/
└── RIVER_OPERATIONS.md       (NEW)

~/phoenix-river/              (UNCHANGED on disk — kept for backwards compat)
```

### Streamer surface — key changes from phoenix

```python
from ..bar_types import NY, UTC
from ...execution.ib.client_id import ClientIdRole, allocate_client_id
from .schema import CANONICAL_PAIRS, get_river_root
from .resubscribe import RiverResubscribeTracker
from .supervisor import RiverSupervisor

class RiverStreamer:
    """Live 1m IBKR bar ingest. ib_insync isolated to this file."""

    def __init__(
        self,
        pair: str = "EURUSD",
        *,
        river_root: Path | None = None,
        ibkr_port: int = 4002,
        supervisor: RiverSupervisor | None = None,
    ):
        if pair not in CANONICAL_PAIRS:
            raise ValueError(f"non-canonical pair: {pair}")
        self._pair = pair
        self._root = river_root or get_river_root()
        self._ibkr_port = ibkr_port
        self._supervisor = supervisor
        self._client_id = allocate_client_id(ClientIdRole.RIVER)   # was random.randint(700,799)
        self._resubscribe = RiverResubscribeTracker()
        # ... phoenix state preserved ...

    def _on_bar_update(self, bars, has_new_bar):
        # ... phoenix logic preserved ...
        if self._supervisor:
            self._supervisor.pulse_heartbeat()    # NEW
```

### RiverSupervisor — thin wrapper over brief 3

```python
class RiverSupervisor(IBKRSupervisor):
    """River-tuned supervisor. Inherits brief-3 threading + halt
    escalation. Gates escalation on market-hours."""

    def __init__(
        self,
        halt_signal: HaltSignal,
        heartbeat_interval: float = 60.0,    # 1m bar cadence
        miss_threshold: int = 3,             # 3 min to DEAD
        check_interval: float = 10.0,
        market_hours_only: bool = True,      # NEW
        **kwargs,
    ): ...

    def _escalate_halt(self, reason: str) -> None:
        if self._market_hours_only and not is_forex_market_open():
            # Off-hours silence is normal. Log but don't escalate.
            if self.on_alert:
                self.on_alert("RIVER_QUIET_OFF_HOURS",
                              f"bars stale during closed market: {reason}")
            return
        super()._escalate_halt(reason)
```

**Tuning vs brief-3 IBKRSupervisor (broker):**

| | Broker (fast escalation) | River (tolerant of normal gaps) |
|---|---|---|
| `heartbeat_interval` | 5.0s | 60.0s (1m bar cadence) |
| `miss_threshold` | 3 (15s to DEAD) | 3 (3 min to DEAD) |
| `check_interval` | 1.0s | 10.0s |
| `market_hours_only` | N/A | True |

**Market-hours gate** uses en1gma's existing forex-day calendar (Sunday 17:00 NY → Friday 17:00 NY). Same boundary as day_state engine.

### RiverResubscribeTracker — mirror of brief-3 ReconnectTracker

| | Broker `ReconnectTracker` (brief 3) | River `RiverResubscribeTracker` |
|---|---|---|
| `backoff_delays` | (5.0, 15.0, 45.0) | (60.0, 120.0, 300.0, 300.0, 300.0) |
| `max_attempts` | 3 | 5 |
| `max_time_sec` | 65.0 | None (phoenix had no time budget) |

Phoenix `RESUBSCRIBE_BACKOFF_S = [60, 120, 300, 300, 300]` and `CONSECUTIVE_GOOD_BARS_RESET = 5` preserved verbatim.

### CLI entry — `start_river_streamer.py`

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", default="EURUSD")
    parser.add_argument("--port", type=int, default=4002)
    parser.add_argument("--no-supervisor", action="store_true")
    args = parser.parse_args()

    halt_signal = HaltSignal()
    supervisor = None
    if not args.no_supervisor:
        supervisor = RiverSupervisor(halt_signal=halt_signal, on_alert=notify_river_alert)
        supervisor.start()

    streamer = RiverStreamer(pair=args.pair, ibkr_port=args.port, supervisor=supervisor)
    try:
        streamer.start()    # blocks
    finally:
        if supervisor:
            supervisor.stop()
```

### launchd plist — `en1gma/launchd/local.river-streamer.plist`

```
Label: com.a8ra.en1gma-river-streamer
ProgramArguments: ["/Users/a8ra_m3/en1gma/.venv/bin/python",
                   "-m", "en1gma.scripts.start_river_streamer",
                   "--pair", "EURUSD", "--port", "4002"]
StandardErrorPath / StandardOutPath: /Users/a8ra_m3/en1gma/logs/river/streamer.log
KeepAlive: { Crashed: true }       ← auto-restart on crash
RunAtLoad: true                    ← start at machine boot
ThrottleInterval: 30
EnvironmentVariables: { RIVER_ROOT: /Users/a8ra_m3/phoenix-river }
```

**Paths CORRECT for this machine** — learn from brief 3 T5 (no `/Users/user/` placeholders).

**Three layers of resilience now:**
1. launchd `KeepAlive` — process restart on crash
2. RiverSupervisor — in-session liveness + halt escalation
3. IBC (brief 3) — Gateway lifecycle

---

## Task Sequence

Order: **schema → synthetic → writer → streamer → seam → supervisor+resubscribe → CLI+launchd → tests+runbook.** Each commit leaves suite green.

### T1 — Schema (CRITICAL)
- **Files created:** `__init__.py`, `schema.py`
- **Changes:** lift `CANONICAL_PAIRS`, `RAW_BAR_SCHEMA`, validators, `get_river_root` (env override, default `~/phoenix-river`)
- **Commit:** `feat(RIVER): lift schema + canonical pairs + bitemporal invariants (T1)`

### T2 — Synthetic (REQUIRED, parallel-safe with T1)
- **Files created:** `synthetic.py`
- **Changes:** lift `synthetic_river.py` for deterministic test bar streams
- **Commit:** `feat(RIVER): lift synthetic bar generator for deterministic test streams (T2)`

### T3 — Writer (CRITICAL)
- **Files created:** `writer.py`
- **Changes:** lift historical writer. structlog → stdlib. clientId via `allocate_client_id(DRILL=99)`. ib_insync gated import. `INV-RIVER-IMMUTABLE` enforced (refuses overwrite).
- **Commit:** `feat(RIVER): lift historical writer — IB → immutable daily parquet (T3)`
- **Gate:** grep `^from ib_insync\|^import ib_insync` en1gma/ → 2 hits

### T4 — Streamer (CRITICAL)
- **Files created:** `streamer.py`
- **Changes:**
  - Lift 718L engine
  - Random clientId 700-799 → `allocate_client_id(RIVER=1)`
  - structlog → stdlib
  - Heartbeat wire format unchanged (consumer compat)
  - Constructor adds optional `supervisor` parameter (wiring deferred to T6)
  - Resubscribe constants preserved inline (T6 extracts)
  - ib_insync gated import
- **Commit:** `feat(RIVER): lift live streamer — IB reqHistoricalData(keepUpToDate=True) → staging JSONL (T4)`
- **Gate:** grep → 3 hits (real_client + writer + streamer)

### T5 — Seam (CRITICAL)
- **Files created:** `seam.py`
- **Changes:** forex-day-close consolidation (17:00 NY). Staging JSONL → immutable parquet. Idempotent re-run safe.
- **Commit:** `feat(RIVER): lift forex-day close seam — staging JSONL → immutable parquet (T5)`

### T6 — Resubscribe + Supervisor (CRITICAL)
- **Files created:** `resubscribe.py`, `supervisor.py`
- **Files modified:** `streamer.py` (consume tracker + supervisor)
- **Changes:**
  - `RiverResubscribeTracker` mirror of brief-3 `ReconnectTracker` with River backoff
  - `RiverSupervisor` extends `IBKRSupervisor`; market-hours gate; River-tuned constants
  - `RiverStreamer` wires both: `supervisor.pulse_heartbeat()` on every `_on_bar_update`, resubscribe path delegates to tracker
- **Commit:** `feat(RIVER): RiverSupervisor + ResubscribeTracker — reuse brief-3 patterns (T6)`

### T7 — CLI + launchd (CRITICAL)
- **Files created:** `start_river_streamer.py`, `local.river-streamer.plist`, `launchd/README.md`
- **Changes:**
  - argparse CLI with `--no-supervisor` flag for dev/debug
  - plist with `KeepAlive: Crashed=true`, `RunAtLoad: true`, `ThrottleInterval: 30`
  - All paths `/Users/a8ra_m3/` (learn from brief 3 T5)
- **Commit:** `feat(RIVER): CLI entry + launchd unit for self-hosted River daemon (T7)`

### T8 — Tests + Runbook (REQUIRED)

| ID | Type | Assertion |
|---|---|---|
| TR01 | unit | `CANONICAL_PAIRS == {EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD}` |
| TR02 | unit | `validate_raw_bars(valid_df)` returns no errors |
| TR03 | unit | missing-column df raises with `INV-RIVER-*` |
| TR04 | unit | `RIVER_ROOT=/tmp/x` → `get_river_root() == Path('/tmp/x')` |
| TR05 | unit | synthetic generates contiguous schema-valid bars |
| TR06 | unit | synthetic deterministic — same seed → same bars |
| TR07 | unit | ResubscribeTracker emits (60,120,300,300,300) then escalates |
| TR08 | unit | reset after `CONSECUTIVE_GOOD_BARS_RESET=5` good bars |
| TR09 | unit | supervisor market-hours gate — weekend silence → no halt, `RIVER_QUIET_OFF_HOURS` alert |
| TR10 | unit | supervisor during market hours → `halt_signal.signal_local` called |
| TR11 | unit | seam consolidates 100 staging bars → parquet with 100 rows |
| TR12 | unit | seam idempotent — second call no-op |
| TR13 | unit | seam rejects rewrite of existing parquet (`INV-RIVER-IMMUTABLE`) |
| TR14 | contract | `RiverStreamer._client_id == 1` (allocator) |
| TR15 | contract | bars via mock IB pass `validate_raw_bars` |
| TR16 | contract | heartbeat JSON has all keys `LiveRiverReader._read_heartbeat` consumes |
| TR17 | integration | `IBKR_INTEGRATION_TEST=1` + Gateway: 5 min run → ≥1 bar in staging, heartbeat connected+subscribed, no halt |
| TR18 | integration | fetch 1 day via writer → parquet created, validate passes, rewrite rejected |

**Runbook contents:**
- How en1gma River relates to brief-2 broker (shared Gateway, distinct clientIds)
- Daily operation (launchd at boot, KeepAlive, supervisor escalation)
- Manual operation
- Backfill operation
- Recovery from supervisor-escalated halt
- Forex-day-close seam mechanics
- Cross-ref to `IB_GATEWAY_OPERATIONS.md`

- **Commit:** `test(RIVER): unit + contract + integration suite + operations runbook (T8)`

---

## Activation Protocol

### Parallel streamer run (validation)

Run en1gma's new streamer **alongside** phoenix's existing streamer (different clientIds = no Gateway collision) for ≥1 forex hour. Both write to the same staging dir. Both dedupe by timestamp — no duplicates.

**Steps:**
1. After T7 commit, plist NOT activated. Foreground launch: `python -m en1gma.scripts.start_river_streamer --pair EURUSD --no-supervisor`
2. Observe heartbeat updates from both streamers (race — but wire format identical, either's update is valid)
3. After ≥1 hour clean parallel: stop phoenix streamer manually, activate plist (`launchctl load en1gma/launchd/local.river-streamer.plist`)
4. Observe en1gma continues solo through next bar update
5. Run brief-2 IB drill — confirms broker still works on its own clientId

**Cutover atomicity:** Two writers safely coexist (dedup + identical wire). After phoenix manual-stop, en1gma is sole writer cleanly.

### Rollback
- **Code primary:** revert T7 (plist) — phoenix never stopped at code layer, only manually; restart phoenix manually to resume
- **Code secondary:** revert T6+T7 — removes supervisor wiring
- **Code full:** revert T1-T8
- **Cutover:** if en1gma misbehaves → `launchctl unload`, restart phoenix manually. No data loss (both write same dir).

---

## Deliverables

**Files created (20):** 8 river-package modules + CLI + plist + launchd README + RIVER_OPERATIONS.md + 7 test files

**Files modified:** consumers of `en1gma/data/river.py` stay unchanged — backwards compat preserved via shim.

**Commits expected:** 8

**Test count delta:** +16 unit + 3 contract (724 → 743 baseline) + 2 integration (env-gated, SKIPPED) + 1 SW19 Sunday-flake unchanged

**`ib_insync` isolation delta:** 1 import file → 3 (real_client + writer + streamer). Documented; invariant updated.

---

## Exit Gates

| Gate | Criterion |
|---|---|
| **G1** SCHEMA_LANDED | `schema.py` exports + `get_river_root` env override (TR01-04) |
| **G2** SYNTHETIC_DETERMINISTIC | Schema-valid contiguous bars; same seed → same bars (TR05-06) |
| **G3** IB_ISOLATION_UPDATED | grep `^from ib_insync\|^import ib_insync` en1gma/ → exactly 3 hits |
| **G4** CLIENTID_FROM_ALLOCATOR | `RiverStreamer._client_id == 1`; no hardcoded clientId outside allocator (TR14 + grep) |
| **G5** RESUBSCRIBE_BACKOFF | Phoenix backoff sequence + escalation (TR07-08) |
| **G6** SUPERVISOR_MARKET_HOURS | Escalates during market; NOT during weekend/holiday (TR09-10) |
| **G7** SEAM_IMMUTABILITY | Consolidate → idempotent → rewrite rejected (TR11-13) |
| **G8** HEARTBEAT_WIRE_COMPAT | All keys `LiveRiverReader` consumes preserved (TR16 + smoke run) |
| **G9** PLIST_VALID | `plutil -lint` clean; all paths `/Users/a8ra_m3/` (no `/Users/user/`) |
| **G10** LIVE_STREAM_SMOKE | `IBKR_INTEGRATION_TEST=1` + Gateway: 5 min run, ≥1 bar, connected+subscribed (TR17) |
| **G11** PARALLEL_CUTOVER_OBSERVED | ≥1 hour parallel + ≥1 hour en1gma-solo, byte-identical bars during overlap (sample 100) |
| **G12** DEFAULT_SUITE_GREEN | pytest full — 743 pass + 2 integration SKIPPED + 1 SW19 flake |

---

## Invariants

### Registered

| Invariant | Statement |
|---|---|
| `INV-RIVER-IMMUTABLE` | Daily parquet at `~/phoenix-river/{PAIR}/{YYYY}/{MM}/{DD}.parquet` are write-once. Re-run is no-op or raises. (Lifted from phoenix; en1gma formalises.) |
| `INV-RIVER-BITEMPORAL` | Every bar carries `world_time` (IBKR market timestamp) AND `knowledge_time` (when we became aware). |
| `INV-RIVER-SOURCE-TAG` | Every bar carries `source` provenance ∈ {dukascopy, ibkr}. Multi-source segregated by `NEX_SOURCE_BOUNDARY` (2025-11-22). en1gma streamer writes `source='ibkr'`. |
| `INV-NO-FORMING-CANDLE` | Streamer NEVER emits a still-forming bar. Persisting one would corrupt the immutable record. |
| `INV-RIVER-CLIENT-ID-1` | River streamer uses `allocate_client_id(RIVER)=1`; writer uses `allocate_client_id(DRILL)=99`. Hardcoded clientId outside allocator = contract violation. Operationalises brief-3 `INV-IBKR-CLIENT-ID-ALLOCATION` for River. |
| `INV-RIVER-MARKET-HOURS-ESCALATION` | RiverSupervisor escalates to halt ONLY during forex market hours. Off-hours silence MUST NOT escalate. |

### Preserved

`INV-HALT-OVERRIDES-ALL`, `INV-GOV-HALT-BEFORE-ACTION`, `INV-IBKR-CLIENT-ID-ALLOCATION` (brief 3 — RIVER now actively allocated), `INV-IBKR-CLIENT-ISOLATION` (extended — 3 import sites each in bounded domain), `INV-IB-TWO-LAYER-RESILIENCE` (broker AND River each have supervisor), `INV-IBKR-FLAKEY-1/2`, `INV-REPLAY-DETERMINISM`

---

## Follow-ups

### `MODULE.RIVER_PATH_RENAME`
Rename `~/phoenix-river/` → `~/river/`. Symlink shim + `RIVER_ROOT` env-flip + grep-rewrite of 19 consumers. Worth doing once en1gma is the indisputable owner.
**Priority:** MEDIUM

### `MODULE.GHOST_POLICY`
Lift phoenix `ghost_policy.py` — gap-fill semantics.
**Priority:** LOW

### `MODULE.RIVER_MULTI_PAIR`
Concurrent multi-pair streaming. Each pair = own streamer instance + own clientId (extend allocator: `RIVER_EURUSD=10`, `RIVER_GBPUSD=11`, ...).
**Priority:** MEDIUM (when scaling beyond EUR/USD)

### `MODULE.RIVER_BACKFILL_AUTOMATION`
Detect missing parquet, fetch from IB, write immutable. Idempotent re-run.
**Priority:** MEDIUM

### `MODULE.SENTINEL_LIVENESS_UPGRADE`
Now both supervisors exist (broker + River), sentinel could consume `supervisor.get_status()` for both.

---

## Notes for Opus

- **LIFT + ADAPT.** Phoenix streamer is the biggest single module (718L). Resist refactoring while lifting. Preserve phoenix logic verbatim except documented changes (clientId allocator, structlog → stdlib, supervisor optional, resubscribe extraction). Refactor passes happen in followup briefs.
- **ON-DISK PATH STAYS `~/phoenix-river/`.** 19+ consumers reference it. Rename is a separate brief. en1gma now OWNS the path; the NAME is historical.
- **`ib_insync` isolation** increases from 1 → 3 files. Intentional. River uses DIFFERENT IB API surface (`reqHistoricalData`) than broker (`placeOrder`). Coupling them through one wrapper conflates concerns.
- **Heartbeat wire format MUST stay compatible** with `LiveRiverReader._read_heartbeat`. Keys `{connected, subscribed, last_bar_time}` preserved. Add new keys freely; don't remove.
- **RiverSupervisor extends IBKRSupervisor** — verify dataclass inheritance works cleanly. Fall back to composition if awkward.
- **Market-hours gate** uses existing en1gma forex calendar (Sunday 17:00 NY → Friday 17:00 NY). If `is_forex_market_open` helper doesn't exist, scope a minimal one in T6.
- **Cutover is the only operational risk.** Both streamers run safely in parallel (distinct clientIds + dedup). Validate ≥1 hour parallel before stopping phoenix. Stop phoenix manually before activating launchd.
- **Three layers of resilience now:** launchd `KeepAlive` (crash restart) + supervisor (in-session liveness) + IBC (Gateway lifecycle). Same logic as `INV-IB-TWO-LAYER-RESILIENCE` applied to River.
- **Do NOT lift `structlog`.** Replace with `logging.getLogger(__name__)`.
- **Synthetic river (T2) lands early** so T8 tests don't depend on parquet fixtures.

---

## Dependencies + Rollback

**Upstream:** MODULE.BROKER_ADAPTER, MODULE.IB_PAPER_ADAPTER, MODULE.IB_CONNECTION_SUPERVISOR (allocator + supervisor pattern)

**Blocks:** MODULE.RIVER_PATH_RENAME, MODULE.GHOST_POLICY, MODULE.RIVER_MULTI_PAIR, MODULE.RIVER_BACKFILL_AUTOMATION, MODULE.SENTINEL_LIVENESS_UPGRADE

**Rollback:**
- **Code primary:** revert T7 — phoenix continues as data source
- **Code secondary:** revert T6+T7 — supervisor wiring removed
- **Code full:** revert T1-T8 — all River-streaming surface removed
- **Cutover:** `launchctl unload` + restart phoenix manually. No data loss.

**Risk:** LOW. Additive code; no behaviour change in existing en1gma surface; backwards-compat shim; cutover validated with parallel run.

---

*Canonical YAML source: `docs/briefs/BRIEF.MODULE.RIVER_IBKR_STREAMER.yaml`*
