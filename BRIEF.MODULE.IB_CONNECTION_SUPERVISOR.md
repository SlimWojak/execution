# BRIEF.MODULE.IB_CONNECTION_SUPERVISOR

| | |
|---|---|
| **Mission** | IB_GATEWAY_RESILIENCE_LAYER |
| **Owner** | Opus (Cursor / factory) |
| **Format** | DENSE |
| **Date** | 2026-05-25 |
| **Series** | `BRIEF.MODULE.*` — third brief in module-by-module sweep |
| **Scope** | Lift phoenix supervisor + heartbeat into en1gma. Add clientId allocator. Reconcile + activate the IBC launchd surface. Wire supervisor → en1gma halt cascade. **Two-layer protection**: IBC owns Gateway process lifecycle; supervisor owns in-session liveness. |

---

## Mission Statement

Brief 2 (`MODULE.IB_PAPER_ADAPTER`) lifts the IB surface and routes PAPER mode through a real IB Gateway. The moment T5 of brief 2 activates, the kernel becomes operationally dependent on a single desktop process (IB Gateway / Jts) that IB itself force-restarts daily and that disconnects routinely under normal conditions.

This brief installs the two-layer resilience that production IB trading requires:

- **LAYER 1 — IBC** (already installed at `/Users/a8ra_m3/ibc/`)
  Gateway process lifecycle. Auto-login with credentials, auto-restart on daily IB-mandated logout, launchd-managed. Owns *"Gateway is even running and logged in."*

- **LAYER 2 — IBKRSupervisor** (lifted from phoenix `supervisor.py`)
  In-session liveness. Heartbeat monitor in a separate thread, watches for connector unresponsiveness, escalates to `halt.signal_local` on persistent failure. Owns *"Gateway is up AND our connection to it is healthy."*

Plus a **clientId allocator** (single source of truth) so River, Broker, COO and drills never collide on the IB API multiplex.

**This is a LIFT + ACTIVATION brief.** Phoenix supervisor/heartbeat are proven (S40 Track B). IBC is fully configured but has two latent defects (plaintext password, placeholder paths in plist) that must be corrected before activation.

---

## Context

**Status in:** expected — clean on main, post-MODULE.IB_PAPER_ADAPTER (708 unit/contract + 2 integration env-gated)

**Sequencing.** Third in the module sweep because:
1. extends the IB surface just landed in brief 2 (same `ib_insync` isolation, same factory seam)
2. unblocks `MODULE.RIVER_IBKR_STREAMER` which needs the clientId allocator
3. IBC plist activation closes the daily-Gateway-restart gap that becomes critical immediately after brief 2's T5

**Out of scope:**
- `MODULE.IB_DEGRADATION` (phoenix `degradation.py` 301L with T2/T1/T0 cascade — separate brief; **this** brief uses single-level escalation to `halt.signal_local` instead)
- `MODULE.IB_LIVE_ADAPTER` (T2 ceremony required)
- `MODULE.IB_BRACKET_ORDERS` (separate brief)
- `MODULE.SENTINEL_LIVENESS_UPGRADE` (independent track — touches `sentinel.py`, not the supervisor module)
- `MODULE.RIVER_IBKR_STREAMER` (lifts in next brief; will USE the allocator added here)
- Phoenix `governance/circuit_breaker.py` + `governance/health_fsm.py` (phoenix-only utilities; this brief strips those deps and uses en1gma halt directly)

---

## Sprawl Audit

### Phoenix supervisor surface

| File | Lines | Verdict |
|---|---|---|
| `phoenix/brokers/ibkr/supervisor.py` | 398 | **LIFT (T4) with simplifications.** Strip phoenix `governance/circuit_breaker` + `governance/health_fsm` + `degradation` imports — replace with direct en1gma halt callback. Keep threading model, `SupervisorState` enum, lock discipline, `SupervisorWatchdog` companion. |
| `phoenix/brokers/ibkr/heartbeat.py` | 252 | **LIFT (T2) wholesale.** Self-contained — only deps are threading + time. `INV-IBKR-FLAKEY-1` preserved. |

**Simplifications applied to supervisor:**
- DROP `DegradationManager` + `DegradationLevel` — single-level escalation (heartbeat DEAD → `on_halt` callback → `halt.signal_local`)
- DROP `HealthStateMachine` — supervisor's own `SupervisorState` enum is sufficient
- DROP `CircuitBreaker` — not used in kernel path
- COLLAPSE `on_degradation` + `on_restore` → `on_alert` (info) + `on_recovery` (info)

### IBC infrastructure present

**`/Users/a8ra_m3/ibc/`** — INSTALLED, fully configured for paper trading. Two latent defects.

| File | Status / Issue | Fix |
|---|---|---|
| `config.ini` | **HIGH:** `IbPassword=1Lovenex1` in plaintext | T5 — blank value, route via env var injected by keychain wrapper |
| `gatewaystartmacos.sh` | Use as-is. Path-correct for this machine (`IBC_PATH=/Users/a8ra_m3/ibc`) | none |
| `check_gateway.sh` | Cron-callable health check (port 4002 + `launchctl start com.a8ra.ibkr-gateway` + max 3 restarts/day). **Calls a launchd label that doesn't match the plist** | T4 — reconcile label (plist takes the script's label) |
| `local.ibc-gateway.plist` | **CRITICAL:** `/Users/user/` placeholder paths throughout — plist will fail as-shipped. Schedule missing `Hour` key. | T4 — rewrite paths to `/Users/a8ra_m3/`, add `Hour=6` NY, rename Label to `com.a8ra.ibkr-gateway` |
| `reconnectaccount.sh`, `reconnectdata.sh`, `stop.sh` | Use as-is — IBC command-sender shims for manual intervention | document in T8 runbook |

### en1gma surface impacted

| File | Status / Change |
|---|---|
| `en1gma/execution/ib/config.py` | **EVOLVED (T3)** — `ReconnectTracker` runtime class lifts here (brief 2 lifted `ReconnectConfig` dataclass only) |
| `en1gma/execution/ib/paper_adapter.py` | **EVOLVED (T7)** — supervisor handle injected, heartbeat pulse on every open/close, reconnect tracker on connect failure, clientId via allocator |
| `en1gma/scripts/run_ars_session.py` | **EVOLVED (T6)** — supervisor + watchdog construction in PAPER mode branch |
| `en1gma/execution/ib/__init__.py` | **EVOLVED** — exports `IBKRSupervisor`, `ClientIdRole`, `allocate_client_id` |
| `en1gma/scripts/sentinel.py` | **UNCHANGED** — sentinel upgrade is a separate independent brief |

### Bloat pruned

- Phoenix `governance/circuit_breaker.py` imports (~50L)
- Phoenix `governance/health_fsm.py` imports (~80L)
- Phoenix `degradation.py` NOT lifted here (entire 301L deferred)
- Multi-tier degradation collapsed to single escalation event

**Net: ~430+ lines simpler than full phoenix lift.**

---

## Target Shape

### Directory layout after brief

```
en1gma/execution/ib/
├── __init__.py          (EVOLVED — exports supervisor + allocator)
├── config.py            (EVOLVED — ReconnectTracker runtime class added)
├── orders.py            (unchanged)
├── positions.py         (unchanged)
├── account.py           (unchanged)
├── real_client.py       (unchanged)
├── paper_adapter.py     (EVOLVED — supervisor + heartbeat wiring)
├── client_id.py         (NEW — allocator)
├── heartbeat.py         (NEW — lifted from phoenix)
└── supervisor.py        (NEW — lifted + simplified from phoenix)
```

Plus IBC corrections out-of-tree:
- `/Users/a8ra_m3/ibc/config.ini` (password → env var)
- `/Users/a8ra_m3/ibc/local.ibc-gateway.plist` (paths + schedule + label)
- `/Users/a8ra_m3/ibc/scripts/launch_with_keychain_password.sh` (NEW wrapper)

Plus operator docs:
- `en1gma/docs/runbooks/IB_GATEWAY_OPERATIONS.md` + IBC templates

### ClientId allocator — `en1gma/execution/ib/client_id.py`

```python
from enum import IntEnum

class ClientIdRole(IntEnum):
    """
    Reserved IBKR API clientId allocations.

    Rationale: ib_insync multiplexes via clientId. Two connections
    with the same clientId silently break.

    Reserved:
      RIVER  = 1   — live bar streaming (MODULE.RIVER_IBKR_STREAMER)
      BROKER = 2   — IBPaperAdapter / IBLiveAdapter
      COO    = 3   — observability / reporting (future)
      DRILL  = 99  — manual validation/roundtrip scripts
    """
    RIVER = 1
    BROKER = 2
    COO = 3
    DRILL = 99

def allocate_client_id(role: ClientIdRole) -> int:
    return int(role)
```

Today's int-mapping is sufficient (single broker process, single River process). The function indirection exists so future multi-connection scenarios can lift to a real allocator without touching call sites.

### Supervisor surface — `en1gma/execution/ib/supervisor.py`

```python
from .heartbeat import HeartbeatMonitor, HeartbeatState
from ...control.halt import HaltSignal

class SupervisorState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    ALERTING = "ALERTING"   # heartbeat DEAD, halt escalated

@dataclass
class IBKRSupervisor:
    """
    Shadow supervisor in separate thread. Watches IB connector
    heartbeat. On miss_threshold misses, fires on_halt callback
    which signals halt.signal_local — INV-HALT-OVERRIDES-ALL stops
    all new trades immediately.

    INV-SUPERVISOR-1, INV-IBKR-FLAKEY-1, INV-IBKR-FLAKEY-2
    """
    halt_signal: HaltSignal
    heartbeat_interval: float = 5.0
    miss_threshold: int = 3
    check_interval: float = 1.0
    on_alert: Callable[[str, str], None] | None = None
    on_recovery: Callable[[], None] | None = None
    # ... start / stop / loop / _escalate_halt ...

class SupervisorWatchdog:
    """Watches the supervisor itself. Alerts on unexpected death."""

def create_ibkr_supervisor(halt_signal, on_alert=None) -> tuple[IBKRSupervisor, SupervisorWatchdog]:
    """Factory returning supervisor + watchdog pair."""
```

**Escalation path:**

On heartbeat DEAD:
1. `supervisor._state` → `ALERTING`
2. `on_alert("IBKR_HEARTBEAT_DEAD", "miss_count=N, last_beat_age=Ts")`
3. `halt_signal.signal_local("ib_supervisor", "heartbeat_dead")`
4. `INV-HALT-OVERRIDES-ALL` kicks in → `IBPaperAdapter.open_position` raises `HaltError` on next call → no new trades placed until heartbeat recovers

On heartbeat recovery while ALERTING:
1. `supervisor._state` → `RUNNING`
2. `on_recovery()`
3. **Halt is NOT auto-cleared** — operator must clear manually. Recovery means the network blip is over, but does NOT mean our position/order state is in sync with IB.

### IBPaperAdapter evolution

```python
class IBPaperAdapter:
    def __init__(
        self,
        halt_signal: HaltSignal,
        config: IBKRConfig,
        fill_timeout_sec: float = 30.0,
        supervisor: IBKRSupervisor | None = None,   # NEW (optional)
    ):
        ...
        self._supervisor = supervisor
        self._client_id = allocate_client_id(ClientIdRole.BROKER)  # NEW

    def _pulse_heartbeat(self) -> None:
        if self._supervisor and self._supervisor.heartbeat:
            self._supervisor.heartbeat.beat()

    def open_position(self, ...):
        self._halt.check()
        self._ensure_connected()
        self._pulse_heartbeat()      # NEW — before submit
        # ... submit + wait for fill ...
        self._pulse_heartbeat()      # NEW — after fill
        return result
```

`supervisor` parameter is OPTIONAL — keeps unit tests broker-less. Production builds (CLI entry points) construct supervisor and pass it in.

### CLI entry wiring — `run_ars_session.py`

```python
if mode == OperatingMode.PAPER:
    from en1gma.execution.ib.supervisor import create_ibkr_supervisor
    supervisor, watchdog = create_ibkr_supervisor(
        halt_signal=halt_signal,
        on_alert=lambda kind, msg: notify(kind, msg),
    )
    supervisor.start()
    watchdog.start()

# ... factory broker construction (unchanged signature) ...
# supervisor handle passed to IBPaperAdapter via constructor param or post-construction setter

try:
    # ... session loop ...
finally:
    supervisor.stop()
    watchdog.stop()
```

### IBC corrections

**`/Users/a8ra_m3/ibc/config.ini`:**
```diff
- IbPassword=1Lovenex1
+ IbPassword=
```
Password read from `IBKR_PASSWORD` env var (set by wrapper script from keychain). `INV-IBKR-CONFIG-1`.

**`/Users/a8ra_m3/ibc/local.ibc-gateway.plist`:**
- Label: `local.ibc-gateway` → `com.a8ra.ibkr-gateway` (matches `check_gateway.sh`)
- Paths: `/Users/user/` → `/Users/a8ra_m3/` throughout
- Schedule: add `Hour=6` (NY-local — between London open and NY open)
- `ProgramArguments` → wrapper script (not `gatewaystartmacos.sh` directly)

**`/Users/a8ra_m3/ibc/scripts/launch_with_keychain_password.sh`** (NEW):
```bash
#!/bin/bash
IBKR_PASSWORD=$(security find-generic-password -a a8ra_m3 -s ibkr_paper -w) \
  exec /Users/a8ra_m3/ibc/gatewaystartmacos.sh "$@"
```

G manual step (T8 runbook): `security add-generic-password -a a8ra_m3 -s ibkr_paper -w '<password>'` before plist activation.

---

## Task Sequence

Order: **allocator → heartbeat → reconnect-tracker → supervisor → IBC-correction → CLI-wiring → adapter-pulse → runbook → tests.** Each commit leaves suite green.

### T1 — ClientId Allocator (CRITICAL)
- **Files created:** `client_id.py`
- **Files modified:** `__init__.py`
- **Commit:** `feat(IB): clientId allocator — single source of truth for IBKR API multiplexing (T1)`

### T2 — Heartbeat Lift (CRITICAL)
- **Files created:** `heartbeat.py`
- **Changes:** lift phoenix `heartbeat.py` wholesale. Strip phoenix-only docstring refs. `INV-IBKR-FLAKEY-1` preserved.
- **Commit:** `feat(IB): lift HeartbeatMonitor from phoenix — INV-IBKR-FLAKEY-1 preserved (T2)`

### T3 — Reconnect Tracker (CRITICAL)
- **Files modified:** `en1gma/execution/ib/config.py`
- **Changes:** lift phoenix `ReconnectTracker` runtime class (accompanies `ReconnectConfig` already in place from brief 2 T1). Method `register_attempt() → delay | escalate=True`.
- **Commit:** `feat(IB): ReconnectTracker runtime — exponential backoff per ReconnectConfig (T3)`

### T4 — Supervisor Lift + Simplify (CRITICAL)
- **Files created:** `supervisor.py`
- **Files modified:** `__init__.py`
- **Changes:**
  - Lift `IBKRSupervisor` + `SupervisorWatchdog` + `create_ibkr_supervisor`
  - **DROP:** `DegradationManager`, `HealthStateMachine`, `CircuitBreaker` deps
  - **REWIRE:** `_trigger_degradation` → `_escalate_halt(reason)` calling `halt_signal.signal_local`
  - Collapse callbacks: `on_alert` (info), `on_recovery` (info), plus mandatory `halt_signal` dependency
  - Preserve: threading model, `SupervisorState` enum, lock discipline, watchdog companion
- **Commit:** `feat(IB): lift IBKRSupervisor + Watchdog from phoenix — escalates to halt.signal_local (T4)`

### T5 — IBC Corrections (HIGH)
- **Files modified (out-of-repo):**
  - `/Users/a8ra_m3/ibc/config.ini` — password → blank
  - `/Users/a8ra_m3/ibc/local.ibc-gateway.plist` — paths, label, schedule
  - `/Users/a8ra_m3/ibc/scripts/launch_with_keychain_password.sh` — NEW wrapper
- **Atomicity:** single commit covering IBC corrections; plist NOT yet loaded into launchd (T8 manual activation).
- **Pre-action:** G backs up `/Users/a8ra_m3/ibc/` via `cp -r ... ibc.bak.$(date +%Y-%m-%d)/`
- **Commit:** `fix(IBC): correct plist paths/label/schedule + remove plaintext password (T5)`

### T6 — CLI Wiring (CRITICAL)
- **Files modified:** `en1gma/scripts/run_ars_session.py`
- **Changes:** in PAPER mode branch, construct supervisor + watchdog via `create_ibkr_supervisor`. Start before broker construction. Stop in `finally` block.
- **Commit:** `feat(IB): supervisor + watchdog wired into run_ars_session PAPER path (T6)`

### T7 — Adapter Heartbeat Pulse (CRITICAL)
- **Files modified:** `paper_adapter.py`
- **Changes:**
  - Add optional `supervisor` parameter to constructor
  - `_pulse_heartbeat` helper (no-op when supervisor is None)
  - Pulse before AND after every `open_position` / `close_position`
  - Use `allocate_client_id(ClientIdRole.BROKER)` in `_ensure_connected`
  - On `client.connect()` failure: instantiate `ReconnectTracker` from `config.reconnect`, retry with backoff, escalate to halt on max attempts
- **Commit:** `feat(IB): IBPaperAdapter heartbeat pulse + reconnect tracker integration (T7)`

### T8 — Operations Runbook (REQUIRED)
- **Files created:**
  - `en1gma/docs/runbooks/IB_GATEWAY_OPERATIONS.md`
  - `en1gma/docs/runbooks/ibc/config.ini.template`
  - `en1gma/docs/runbooks/ibc/local.ibc-gateway.plist.template`
  - `en1gma/docs/runbooks/ibc/launch_with_keychain_password.sh.template`
- **Commit:** `docs(IB): two-layer gateway resilience runbook + IBC templates (T8)`

### T9 — Tests (REQUIRED)

| ID | Type | Assertion |
|---|---|---|
| TS01-04 | unit | `allocate_client_id(BROKER)==2`, `(RIVER)==1`, `(COO)==3`, `(DRILL)==99` |
| TS05-07 | unit | HeartbeatMonitor: beat → ALIVE; no beats → DEAD; recover → ALIVE + `on_recovery` |
| TS08 | unit | supervisor start/stop clean, thread joined within 5s |
| TS09 | unit | heartbeat DEAD escalates → `halt_signal.signal_local` called once |
| TS10 | unit | recovery returns RUNNING but halt **NOT** auto-cleared |
| TS11 | unit | `on_alert` raises → supervisor loop continues (INV-IBKR-FLAKEY-2) |
| TS12 | unit | watchdog fires `on_supervisor_dead` when supervisor dies |
| TS13-16 | unit | ReconnectTracker backoff sequence, escalation at max attempts, time-budget escalation, reset |
| TS17 | integration | with `IBKR_INTEGRATION_TEST=1` + Gateway: kill Gateway mid-session → supervisor ALERTING → halt active → `HaltError` on next `open_position` |

- **Commit:** `test(IB): supervisor + heartbeat + allocator + reconnect tracker suite (T9)`

---

## Activation Protocol

### Layer 1 — IBC activation (G manual after T5 + T8)
1. `security add-generic-password -a a8ra_m3 -s ibkr_paper -w '<password>'`
2. Dry-run wrapper: `bash /Users/a8ra_m3/ibc/scripts/launch_with_keychain_password.sh --dry-run`
3. Stop any running Gateway: `bash /Users/a8ra_m3/ibc/stop.sh`
4. Install plist: `launchctl load /Users/a8ra_m3/ibc/local.ibc-gateway.plist`
5. Trigger immediate run: `launchctl start com.a8ra.ibkr-gateway` — observe Gateway window, login, port 4002 listening
6. Verify with `bash /Users/a8ra_m3/ibc/check_gateway.sh` → ✅ Gateway UP
7. Run brief-2 drill: `python -m en1gma.scripts.drills.ib_paper_validation`

### Layer 2 — Supervisor activation
After T6+T7: supervisor activates automatically on every PAPER `run_ars_session`. No manual step.

**First session observation:**
- New Telegram alerts: `supervisor_started` at start, `supervisor_stopped` at end
- Throughout: heartbeat pulses on every broker open/close, no alert spam
- Any `IBKR_HEARTBEAT_DEAD` alert during a healthy session = defect, root-cause before resuming

### Rollback safety
- **Code:** revert T7 alone (drops pulses + reconnect tracker, supervisor module stays dormant); or T6+T7; or full T1-T9
- **IBC:** restore from backup; `launchctl unload local.ibc-gateway.plist`

---

## Deliverables

**Files created (13):** allocator, heartbeat, supervisor + 4 runbook artifacts + 5 test files

**Files modified (4 in-repo):** `__init__.py`, `config.py`, `paper_adapter.py`, `run_ars_session.py`

**Files modified (out-of-repo):** `ibc/config.ini`, `ibc/local.ibc-gateway.plist`, plus new `ibc/scripts/launch_with_keychain_password.sh`

**Commits expected:** 9

**Test count delta:** +16 unit (708 → 724) + 1 integration (env-gated, SKIPPED by default) + 1 SW19 Sunday-flake unchanged

---

## Exit Gates

| Gate | Criterion |
|---|---|
| **G1** ALLOCATOR_CANONICAL | `ClientIdRole` enum matches `{RIVER=1, BROKER=2, COO=3, DRILL=99}` |
| **G2** HEARTBEAT_FSM_CORRECT | Transitions ALIVE → DEAD after `miss_threshold * interval` without beat; `beat()` restores |
| **G3** SUPERVISOR_ESCALATES_HALT | Heartbeat DEAD → `halt_signal.signal_local` called once. Halt NOT auto-cleared on recovery. |
| **G4** SUPERVISOR_SURVIVES | `INV-IBKR-FLAKEY-2` (loop survives callback raise) + `INV-SUPERVISOR-1` (watchdog fires on death) |
| **G5** RECONNECT_BACKOFF | `ReconnectTracker` emits declared backoff; escalates on max_attempts OR max_time_sec |
| **G6** IBC_PLIST_VALID | `plutil -lint /Users/a8ra_m3/ibc/local.ibc-gateway.plist` — no syntax errors |
| **G7** IBC_PASSWORD_PURGED | `grep -r '1Lovenex1' /Users/a8ra_m3/ibc/` → zero matches. Password in keychain only. |
| **G8** IBC_LAUNCHD_VALIDATED | Post G activation: `launchctl list \| grep com.a8ra.ibkr-gateway` shows job loaded; `check_gateway.sh` reports ✅ |
| **G9** FIRST_SUPERVISED_SESSION | First PAPER ARS session post-T6+T7 runs end-to-end. `supervisor_started` observed at start, `supervisor_stopped` at end, no spurious halts. |
| **G10** GATEWAY_KILL_RECOVERY | TS17 (env-gated): kill Gateway → halt active → `HaltError` on next call |
| **G11** DEFAULT_SUITE_GREEN | pytest full — 724 pass + integration SKIPPED + 1 SW19 flake. Zero regressions. |

---

## Invariants

### Registered

| Invariant | Statement |
|---|---|
| `INV-IBKR-FLAKEY-1` | HeartbeatMonitor declares DEAD after 3 consecutive missed beats (configurable). DEAD = trigger for supervisor halt escalation. |
| `INV-IBKR-FLAKEY-2` | Supervisor loop wrapped in try/except — callback raises do NOT terminate the loop. Supervisor survives any connector or callback crash. |
| `INV-SUPERVISOR-1` | Supervisor unexpected death triggers `on_supervisor_dead` alert within `watchdog.check_interval`. Watchdog is a separate thread that survives the supervisor. |
| `INV-IBKR-CLIENT-ID-ALLOCATION` | `clientId` values allocated via `allocate_client_id`. Hardcoded `clientId` outside `client_id.py` is a contract violation. RIVER=1, BROKER=2, COO=3, DRILL=99. (Promoted from inline note in brief 2 to fully enforced.) |
| `INV-IBKR-RECONNECT-1` | Connection failures retry per `ReconnectConfig.backoff_delays`. Max attempts OR `max_time_sec` triggers escalation to `halt.signal_local`. No infinite retry loops. |
| `INV-IB-TWO-LAYER-RESILIENCE` | IB Gateway resilience = LAYER 1 (IBC + launchd, process lifecycle) + LAYER 2 (IBKRSupervisor in-process, in-session liveness). Neither sufficient alone: Layer 1 can't detect a TCP-responding-but-API-hung connection; Layer 2 can't restart a dead Gateway process. |
| `INV-IBKR-CONFIG-1` (strengthened) | Production password lives in macOS keychain ONLY; retrieved at IBC launch via wrapper script. Brief 2 introduced this invariant; this brief operationalises it by purging plaintext password from `config.ini`. |

### Preserved

`INV-HALT-OVERRIDES-ALL`, `INV-GOV-HALT-BEFORE-ACTION`, `INV-BROKER-PROTOCOL-IS-CONTRACT`, `INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE`, `INV-IBKR-CLIENT-ISOLATION`, `INV-PAPER-GOVERNANCE-PARITY-WITH-LIVE`, `INV-MODE-EXPLICIT-PER-INVOCATION`, `INV-REPLAY-DETERMINISM`

---

## Follow-ups

### `MODULE.RIVER_IBKR_STREAMER`
Lift `phoenix/river/streamer.py` `reqHistoricalData` streaming. Uses `allocate_client_id(ClientIdRole.RIVER)` — directly consumes this brief's allocator. **G's stated river-pipeline focus.** Brief 4.
**Prerequisites:** this brief

### `MODULE.IB_DEGRADATION`
Lift phoenix `degradation.py` (301L). T2/T1/T0 cascade for graceful capability reduction. Layered above single-level halt escalation.
**Prerequisites:** this brief
**Note:** Optional refinement. Single-level escalation is sufficient for first paper operation.

### `MODULE.IB_LIVE_ADAPTER`
`IBLiveAdapter` re-uses entire resilience layer from this brief. Differences: port 4001, U* prefix, T2 token gating.
**Prerequisites:** this brief + `T2_CEREMONY_CONTRACT`

### `MODULE.SENTINEL_LIVENESS_UPGRADE`
With supervisor in place, sentinel could consume `supervisor.get_status()` instead of doing its own check — single source of truth for IB liveness.

### `MODULE.POSITION_LIFECYCLE_EXTENSION`
Async fill states. Prereq for `MODULE.IB_BRACKET_ORDERS`.

### `MODULE.KEYCHAIN_CREDENTIAL_STORE`
Generalise the keychain wrapper into a shared credential-retrieval module (LOW priority).

---

## Notes for Opus

- **LIFT + SIMPLIFY.** Phoenix supervisor is PROVEN but drags four governance utilities (`circuit_breaker`, `health_fsm`, `degradation`, alert callbacks) that en1gma does NOT need. Strip aggressively. Single-level escalation to `halt.signal_local` is the kernel idiom.
- **Threading is intentional.** Supervisor MUST run in a separate thread (not asyncio task on main loop) so it survives connector blocking. Preserve `daemon=True` thread + Lock discipline verbatim.
- **Heartbeat pulse location matters.** Pulse BEFORE AND AFTER every network call. Before-only means hung submit undetected for `interval * miss_threshold` seconds. After-only means hung submit not treated as activity. **Both.**
- **Halt-on-recovery policy:** do NOT auto-clear halt when heartbeat recovers. Recovery means network blip is over, NOT that internal state is in sync with IB. Operator must manually inspect.
- **IBC password — DO NOT put it in plist `EnvironmentVariables`.** No better than `config.ini`. Use wrapper script that reads from macOS keychain via `security` command, exports `IBKR_PASSWORD`, execs IBC launcher.
- **Out-of-repo files** (`/Users/a8ra_m3/ibc/*`) — T5 commit message includes verbatim diff for G to apply manually under guidance. T8 includes templates in `en1gma/docs/runbooks/ibc/`.
- **Before T5:** G backs up `/Users/a8ra_m3/ibc/` via `cp -r ... ibc.bak.$(date +%Y-%m-%d)/`. Mention in T5 commit message.
- **plist `Hour=6` NY-local:** launchd uses system local timezone. Verify G's machine is set to NY (recommended) in T8 runbook.
- **Reconnect vs Supervisor — distinct concerns:**
  - RECONNECT (`ReconnectTracker`) handles *"connection attempt failed, retry with backoff."* Inside `IBPaperAdapter._ensure_connected`.
  - SUPERVISOR handles *"established connection went silent."* Separate thread, watches heartbeat.
  - Both can independently escalate to halt.
- **ARS daemon already runs PAPER under launchd** (SW09). After T6, that daemon constructs a supervisor. Verify supervisor stops cleanly on abnormal session end — use `try/finally` in CLI entry.
- **First post-T6+T7 PAPER session is the litmus test.** G observes manually. Expected new alerts: `SUPERVISOR_STARTED`/`STOPPED`, no escalations during normal operation.

---

## Dependencies + Rollback

**Upstream:** MODULE.BROKER_ADAPTER, MODULE.IB_PAPER_ADAPTER, SW08

**Blocks:** MODULE.RIVER_IBKR_STREAMER (needs allocator), MODULE.IB_DEGRADATION (refines escalation), MODULE.IB_LIVE_ADAPTER (re-uses supervisor), MODULE.SENTINEL_LIVENESS_UPGRADE (can consume supervisor status)

**Rollback:**
- **Code primary:** revert T7 only — adapter loses pulses + reconnect tracker, returns to brief-2 baseline. Supervisor module stays landed but unused.
- **Code secondary:** revert T6+T7 — CLI no longer constructs supervisor.
- **Code full:** revert T1-T9.
- **IBC:** restore from backup; `launchctl unload local.ibc-gateway.plist`

**Risk:**
- Code: LOW (additive; T7 only behaviour-altering change to existing module)
- IBC: MEDIUM (out-of-repo + manual activation; mitigated by backup + runbook + plist syntax validation in G6)

---

*Canonical YAML source: `docs/briefs/BRIEF.MODULE.IB_CONNECTION_SUPERVISOR.yaml`*
