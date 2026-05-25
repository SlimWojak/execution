# BRIEF.MODULE.IB_PAPER_ADAPTER

| | |
|---|---|
| **Mission** | REAL_IBKR_PAPER_BROKER_INTEGRATION |
| **Owner** | Opus (Cursor / factory) |
| **Format** | DENSE |
| **Date** | 2026-05-25 |
| **Series** | `BRIEF.MODULE.*` — second brief in module-by-module sweep |
| **Scope** | Lift proven phoenix IBKR core (config/clients/orders/positions/account) into en1gma. Wrap as `IBPaperAdapter` implementing `BrokerAdapter` Protocol. Wire into factory for `PAPER` mode. **PAPER ACCOUNT ONLY** — `LIVE` remains `NotImplementedError` per SW08. |

---

## Mission Statement

Phoenix already has 3,339 lines of production IBKR integration code (S33 phase, fully proven via drills that round-trip live IB paper orders). This brief **LIFTS** the core surface — config, connector, real_client, orders, positions, account — into `en1gma/execution/ib/`, wraps it behind a thin `IBPaperAdapter` that implements the `BrokerAdapter` Protocol, and evolves the factory so PAPER mode dispatches to real IB instead of in-memory.

Synchronous fill semantics preserved (matches today's `PaperBroker` surface — submit → block on fill or timeout → return `OrderResult`). No async lifecycle refactor in this brief; that's `MODULE.POSITION_LIFECYCLE_EXTENSION`. No bracket orders; that's `MODULE.IB_BRACKET_ORDERS`. No connection supervisor / IBC wiring; those are `MODULE.IB_CONNECTION_SUPERVISOR` and `MODULE.IBC_LIFECYCLE_SUPERVISOR`.

**This is a LIFT-AND-RESHAPE brief, not a write-from-scratch brief.** The hard work was done in phoenix S33. We are extracting the leanest functional core and stripping phoenix-specific machinery (bead emission, phoenix T2 token store, phoenix governance hooks) that en1gma already provides through different modules.

---

## Context

**Status in:** expected — clean on main, 697 tests passing (post-MODULE.BROKER_ADAPTER)

**Sequencing.** This brief is the SECOND in the module sweep, immediately after MODULE.BROKER_ADAPTER. **Do not start this brief until the prior one ships** (5 commits, +8 tests, factory + Protocol in place).

**Out of scope:**
- `MODULE.IB_LIVE_ADAPTER` (LIVE mode, T2 ceremony — separate brief, gated by Q3 ruling)
- `MODULE.IB_BRACKET_ORDERS` (native SL/TP at broker — separate brief, requires Position FSM extension)
- `MODULE.IB_CONNECTION_SUPERVISOR` (reconnect tracker, clientId allocator, IBC plist — separate brief)
- `MODULE.IB_DEGRADATION` (phoenix degradation.py 301L — separate brief, on top of supervisor)
- `MODULE.IBC_LIFECYCLE_SUPERVISOR` (wire `/Users/a8ra_m3/ibc` launchd plist — separate brief)
- `MODULE.POSITION_LIFECYCLE_EXTENSION` (async fill states — separate brief; currently OPEN stamped at submission time same as PaperBroker)
- `MODULE.SENTINEL_LIVENESS_UPGRADE` (TCP → API roundtrip — independent track)
- `MODULE.RIVER_IBKR_STREAMER` (phoenix-river uses a separate ib_insync connection for `reqHistoricalData` — separate followup brief)
- Phoenix `mock_client.py` (`PaperBroker` fills the in-memory testing slot)
- Phoenix `session_bead.py` (en1gma uses decision_trace + notification queue)
- Phoenix T2 token store (en1gma's T2 ceremony is a separate contract per SW08 Q3)

---

## Sprawl Audit — Phoenix `brokers/ibkr/`

`/Users/a8ra_m3/phoenix/brokers/ibkr/` — **3,339 lines total, S33 PROVEN.**

### Lift directly

| File | Lines | Role | Verdict |
|---|---|---|---|
| `config.py` | 309 | `IBKRConfig` + `IBKRMode` + `ReconnectConfig` + paper guards + env loading | **LIFT (T1).** Keep IBKRMode internal to en1gma/execution/ib/ as a broker-config concern (distinct from runtime `OperatingMode`). Strip the runtime `ReconnectTracker` machine — lifts later. |
| `orders.py` | 175 | `Order`, `OrderResult`, `OrderStatus`, `OrderSide`, `OrderType` | **LIFT (T2)** as `IBOrder`/`IBOrderResult`/etc. to avoid collision with en1gma's `OrderResult` from `broker_protocol.py`. Strip `token_id` field (PAPER doesn't need T2). |
| `positions.py` | 115 | `Position` + `PositionSnapshot` | **LIFT (T2)** as `IBPosition`/`IBPositionSnapshot` to avoid collision with en1gma's `execution/position.py Position` FSM (different concept — internal trade record vs IB account row). |
| `account.py` | 105 | `AccountState` | **LIFT (T2).** No collision. |
| `real_client.py` | 456 | `ib_insync` wrapper — sole `ib_insync` importer | **LIFT (T3).** Strip phoenix logging idioms; preserve isolation discipline (only file in tree that imports `ib_insync`). |

### Cherry-pick

| File | Lines | Verdict |
|---|---|---|
| `connector.py` | 544 | **DO NOT LIFT WHOLESALE.** Cherry-pick paper-guard + account-validation + order-submission logic (~200L) into `IBPaperAdapter` (T4). Strip T2 token validation (en1gma governance handles this), bead emission (en1gma uses decision_trace), reconnect machine (deferred), AlertCallback (en1gma uses notification queue). |

### Do not lift / defer

| File | Lines | Verdict |
|---|---|---|
| `mock_client.py` | 393 | **DO NOT LIFT** — en1gma `PaperBroker` (110L) already fills this slot, leaner and satisfies `BrokerAdapter` Protocol. |
| `session_bead.py` | 224 | **PRUNE** — en1gma uses decision_trace + notification_queue. Do not lift at all. |
| `supervisor.py` | 398 | **DEFER** → `MODULE.IB_CONNECTION_SUPERVISOR`. Manual reconnect via daemon restart is acceptable for first paper integration. |
| `degradation.py` | 301 | **DEFER** → `MODULE.IB_DEGRADATION`. Layers on top of supervisor. |
| `heartbeat.py` | 252 | **DEFER** — mostly subsumed by `MODULE.SENTINEL_LIVENESS_UPGRADE`. |

### Drills (`/Users/a8ra_m3/phoenix/drills/`)

| File | Lines | Verdict |
|---|---|---|
| `ibkr_paper_validation.py` | 387 | **LIFT + ADAPT (T6)** → `en1gma/scripts/drills/ib_paper_validation.py`. Strip bead emission; reroute config; assert `IBPaperAdapter` directly via Protocol surface. |
| `ibkr_paper_trade_roundtrip.py` | 422 | **LIFT + ADAPT (T6)** → `en1gma/scripts/drills/ib_paper_roundtrip.py`. Strip T2 token store dep + bead emission; route through `IBPaperAdapter`. |

### Out of scope (other phoenix IB users)

`phoenix/river/streamer.py` — separate `ib_insync` connection for `reqHistoricalData` (bar streaming, not order submission). Will share the Gateway but holds a distinct clientId. Lift in `MODULE.RIVER_IBKR_STREAMER`.

### Bloat pruned by this brief

- `mock_client.py` (393L) — superseded by en1gma `PaperBroker`
- `session_bead.py` (224L) — superseded by en1gma decision_trace
- Connector T2 token paths (~50L)
- Connector `AlertCallback` (~30L)
- Connector reconnect plumbing (~80L)

**Net: phoenix surface 3,339L → en1gma surface ~1,500L** (~777 lines explicitly dropped, supervisor/degradation/heartbeat deferred to follow-up briefs).

### Infrastructure (unchanged in this brief)

- `/Users/a8ra_m3/Jts/` — IB Gateway runtime, installed + launching daily (G manual). Must be running for `IBPaperAdapter` to function.
- `/Users/a8ra_m3/ibc/` — IBController installed, plist not activated. Out of scope (covered by `MODULE.IBC_LIFECYCLE_SUPERVISOR`).

---

## Target Shape

### Directory layout

```
en1gma/execution/
├── broker_adapter.py            (unchanged — PaperBroker)
├── broker_protocol.py           (unchanged — BrokerAdapter)
├── broker_factory.py            (EVOLVED — T5)
├── position.py                  (unchanged — internal Position FSM)
├── intent_builder.py            (unchanged)
└── ib/
    ├── __init__.py              (NEW — exports IBPaperAdapter, IBKRConfig)
    ├── config.py                (NEW — lifted, ~250L)
    ├── orders.py                (NEW — IBOrder + IBOrderStatus, ~150L)
    ├── positions.py             (NEW — IBPosition + IBPositionSnapshot, ~100L)
    ├── account.py               (NEW — AccountState, ~90L)
    ├── real_client.py           (NEW — ib_insync wrapper, ~400L)
    └── paper_adapter.py         (NEW — IBPaperAdapter BrokerAdapter wrapper, ~200L)
```

### `IBPaperAdapter` surface — `en1gma/execution/ib/paper_adapter.py`

```python
from ...control.halt import HaltSignal
from ..broker_protocol import BrokerAdapter, OrderResult, ExitResult
from .config import IBKRConfig, IBKRMode
from .real_client import RealIBKRClient

class IBPaperAdapter:
    """
    Real IB paper-account adapter implementing BrokerAdapter.

    Synchronous fill semantics: open_position blocks up to
    fill_timeout_sec waiting for IB fill confirmation, then
    returns OrderResult with fill_price.

    INVARIANTS:
      INV-GOV-HALT-BEFORE-ACTION
      INV-IBKR-PAPER-GUARD-1
      INV-IBKR-ACCOUNT-CHECK-1
      INV-IBKR-CLIENT-ISOLATION
    """

    def __init__(
        self,
        halt_signal: HaltSignal,
        config: IBKRConfig,
        fill_timeout_sec: float = 30.0,
    ):
        if config.mode != IBKRMode.PAPER:
            raise ValueError(f"IBPaperAdapter requires PAPER mode, got {config.mode}")
        self._halt = halt_signal
        self._config = config
        self._client = RealIBKRClient(config)
        self._fill_timeout = fill_timeout_sec
        self._positions: dict[str, Position] = {}
        self._counter = 0
        self._connected = False

    def _ensure_connected(self) -> None:
        if not self._connected:
            if not self._client.connect():
                raise ConnectionError(
                    f"IB Gateway connection failed — is Gateway running on "
                    f"{self._config.host}:{self._config.port}?"
                )
            account_id = self._client.account_id
            valid, err = self._config.validate_account(account_id)
            if not valid:
                self._client.disconnect()
                raise ValueError(err)
            self._connected = True

    def open_position(self, symbol, direction, size, entry_price) -> OrderResult:
        self._halt.check()
        self._ensure_connected()
        # submit IBOrder market → block on fill up to fill_timeout_sec →
        # return OrderResult(success, position_id, fill_price)

    def close_position(self, position_id, exit_price, reason="exit") -> ExitResult: ...
    def halt_all(self, halt_id: str) -> int: ...
    def get_total_pnl(self) -> dict[str, float]: ...
```

### Factory evolution — semantic shift

```python
# Before this brief (post-MODULE.BROKER_ADAPTER):
def build_broker(mode, halt) -> BrokerAdapter:
    if mode in (TEST, SHADOW, PAPER):
        return PaperBroker(halt)
    if mode == LIVE:
        raise NotImplementedError(...)

# After this brief:
def build_broker(mode, halt) -> BrokerAdapter:
    if mode in (OperatingMode.TEST, OperatingMode.SHADOW):
        return PaperBroker(halt)
    if mode == OperatingMode.PAPER:
        from .ib.paper_adapter import IBPaperAdapter  # lazy
        from .ib.config import IBKRConfig
        return IBPaperAdapter(halt_signal=halt, config=IBKRConfig.from_env())
    if mode == OperatingMode.LIVE:
        raise NotImplementedError("see MODULE.IB_LIVE_ADAPTER brief")
```

**What changes:**
- **BEFORE:** `PAPER` → in-memory PaperBroker (synthetic fills)
- **AFTER:** `PAPER` → IBPaperAdapter (real IB paper account fills)

**What stays:**
- `TEST` → in-memory PaperBroker (test environments don't need IB Gateway)
- `SHADOW` → in-memory PaperBroker (decision-only paths)
- Backtest / replay continues using `TEST` or `SHADOW` (synthetic fills)
- ARS live session in `PAPER` mode promotes from synthetic to real-IB-paper

**Why this split:** Replay/backtest needs deterministic synthetic fills (no network, no Gateway dep). SHADOW is the decision-only path. PAPER is the dress rehearsal for LIVE — and dress rehearsals must use real broker plumbing or they don't catch the real failure modes (connection drops, fill latency, rejection codes, partial fills, IB-side risk limits). This split is the operational embodiment of `INV-PAPER-GOVERNANCE-PARITY-WITH-LIVE`.

### Env var contract

Required for PAPER mode:
- `IBKR_MODE=PAPER`
- `IBKR_HOST=127.0.0.1` (default)
- `IBKR_PORT=4002` (default — Gateway paper port)
- `IBKR_CLIENT_ID=2` (en1gma broker reserves clientId=2; River=1 future)

Enforced by `IBKRConfig.from_env()` and `IBKRConfig.validate_startup()`. `.env.example` checked into repo; real `.env` stays gitignored. `INV-IBKR-CONFIG-1`.

---

## Task Sequence

Order: **dep declaration → pure dataclasses → ib_insync wrapper → adapter → factory → drills → tests.** Each commit leaves suite green.

### T1 — Dep + Skeleton + Config (CRITICAL)
- **Files created:** `en1gma/execution/ib/__init__.py`, `en1gma/execution/ib/config.py`, `.env.example`
- **Files modified:** `pyproject.toml` (add `ib_insync` dep)
- **Changes:** lift `IBKRConfig` + `IBKRMode` + `ReconnectConfig` dataclasses (strip runtime `ReconnectTracker`, phoenix bead imports). Default clientId 1 → 2 (reserve 1 for River).
- **Atomicity:** dep + config-only. No `ib_insync` import yet — `config.py` has zero `ib_insync` surface.
- **Commit:** `feat(IB): add ib_insync dep + lift IBKRConfig/IBKRMode to en1gma/execution/ib/ (T1)`

### T2 — Data Types (CRITICAL)
- **Files created:** `orders.py`, `positions.py`, `account.py` under `en1gma/execution/ib/`
- **Changes:**
  - `Order → IBOrder`, `OrderResult → IBOrderResult`, `OrderStatus → IBOrderStatus`, `OrderSide → IBOrderSide`, `OrderType → IBOrderType` (strip `token_id`)
  - `Position → IBPosition`, `PositionSnapshot → IBPositionSnapshot` (avoid collision with `execution/position.py`)
  - `AccountState` lifted as-is
- **Atomicity:** pure dataclasses, no `ib_insync`, no behaviour.
- **Commit:** `feat(IB): lift IB data types (IBOrder, IBPosition, AccountState) (T2)`

### T3 — Real Client (CRITICAL)
- **Files created:** `en1gma/execution/ib/real_client.py`
- **Changes:** lift phoenix `real_client.py`. Strip phoenix logging idioms; preserve `ib_insync` isolation. Update internal references to T2 renamed types. Guard `ib_insync` import — clear error at construction time, not import time.
- **Atomicity:** `real_client` standalone. Not yet wired anywhere in production paths.
- **Commit:** `feat(IB): lift RealIBKRClient (ib_insync wrapper) — sole ib_insync importer (T3)`
- **Gate:** `grep -r 'from ib_insync' en1gma/` → exactly 1 hit (`real_client.py`)

### T4 — Paper Adapter (CRITICAL)
- **Files created:** `en1gma/execution/ib/paper_adapter.py`
- **Files modified:** `en1gma/execution/ib/__init__.py` (export `IBPaperAdapter`, `IBKRConfig`)
- **Changes:** implement `IBPaperAdapter` satisfying `BrokerAdapter` Protocol. Constructor `(halt, config, fill_timeout_sec=30.0)`. Lazy connect on first `open_position`. Halt-check → ensure connected → submit `IBOrder` market → block on fill → return `OrderResult`. `close_position` mirrors with opposing order + realized P&L. `halt_all` disconnects + marks internal positions HALTED. `get_total_pnl` queries IB.
- **Atomicity:** adapter standalone — factory still returns `PaperBroker` for PAPER (factory change is T5).
- **Commit:** `feat(IB): IBPaperAdapter implementing BrokerAdapter Protocol (T4)`

### T5 — Factory Evolution (CRITICAL)
- **Files modified:** `en1gma/execution/broker_factory.py`
- **Changes:** PAPER branch dispatches to `IBPaperAdapter` (was `PaperBroker`). SHADOW + TEST unchanged. LIVE unchanged. **Lazy import** of `IBPaperAdapter` inside the PAPER branch so TEST/SHADOW callers don't pay `ib_insync` import cost.
- **Atomicity:** single semantic change. Consequences large — every PAPER-mode invocation now requires IB Gateway running. See **activation protocol** below.
- **Commit:** `feat(IB): factory PAPER branch dispatches to IBPaperAdapter (T5)`

### T6 — Drill Scripts (REQUIRED)
- **Files created:** `en1gma/scripts/drills/__init__.py`, `ib_paper_validation.py`, `ib_paper_roundtrip.py`
- **Changes:** lift phoenix drills, strip bead emission + phoenix T2 token store dep, route through `IBPaperAdapter`. EUR/USD 20k fixed test order. Capture verbatim PASS output in commit message.
- **Atomicity:** two scripts in one commit.
- **Commit:** `feat(IB): lift IB paper validation + round-trip drills as en1gma scripts (T6)`

### T7 — Test Suite (REQUIRED)
- **Files created:** `test_ib_paper_adapter.py`, `test_ib_config.py`, `test_ib_paper_adapter_protocol.py`, `test_ib_paper_roundtrip.py` (env-gated)

| ID | Type | Assertion |
|---|---|---|
| TI01 | unit | `IBKRConfig.from_env()` with no env → MOCK mode |
| TI02 | unit | `IBKR_MODE=PAPER` → mode=PAPER, port=4002, prefix=DU |
| TI03 | unit | `IBKR_MODE=LIVE` without `IBKR_ALLOW_LIVE` → `validate_startup` fails with `INV-IBKR-PAPER-GUARD-1` |
| TI04 | unit | `validate_account('DU1234567')` in PAPER → valid |
| TI05 | unit | `validate_account('U9999999')` in PAPER → rejected |
| TI06 | unit | `IBPaperAdapter(halt, mock_config)` raises `ValueError` |
| TI07 | unit | halt active → `open_position` raises `HaltError` before connect attempt |
| TI08 | contract | `isinstance(IBPaperAdapter(halt, paper_config), BrokerAdapter)` is True |
| TI09 | contract | `build_broker(PAPER, halt)` returns `IBPaperAdapter`, not `PaperBroker` |
| TI10 | contract | `build_broker(SHADOW, halt)` still returns `PaperBroker` |
| TI11 | contract | `build_broker(TEST, halt)` still returns `PaperBroker` |
| TI12 | integration | with `IBKR_INTEGRATION_TEST=1` + Gateway: open EURUSD 20k market → fill within 30s, `OrderResult.success` True, `fill_price > 0` |
| TI13 | integration | with `IBKR_INTEGRATION_TEST=1`: open → close round-trip → `ExitResult.success` True, `realized_pnl` computed |

- **Atomicity:** unit + contract + integration in one commit (integration via `@pytest.mark.integration` + skip-unless-env). Default pytest does NOT require Gateway.
- **Commit:** `test(IB): IBPaperAdapter unit + contract + env-gated integration suite (T7)`

---

## Activation Protocol

T5 changes the meaning of PAPER mode. Controlled rollout:

**Pre-T5 verification:**
- Run `en1gma/scripts/drills/ib_paper_validation.py` manually against G's Gateway → all 5 checks PASS
- Run `en1gma/scripts/drills/ib_paper_roundtrip.py` manually → full BUY→FILL→SELL→FLAT PASS
- Verify `.env`: `IBKR_MODE=PAPER`, `IBKR_CLIENT_ID=2`, `IBKR_HOST=127.0.0.1`
- Verify ARS daemon NOT currently running (no live session in flight)

**Rollout order:**
1. Ship T1-T4 + T6-T7 (no factory change yet). Manual drill PASS confirms IB adapter works.
2. Ship T5 (factory evolution). PAPER mode now routes to `IBPaperAdapter`.
3. **First ARS live session post-T5 observed manually by G.** Expected: SESSION_START → ASIA_COMPLETE → SETUP_FOUND → real IB order submitted → fill notification from IB → TRADE_PLACED with real fill_price → bar-by-bar SL/TP monitoring (unchanged from PaperBroker path).
4. If anything misbehaves: hot rollback via `git revert` on T5 alone — restores `PaperBroker` for PAPER; rest of IB surface stays landed (dormant).

**Rollback safety:** T5 is a single-commit change so it can be reverted in isolation. T1-T4 + T6-T7 add IB surface without activating it.

---

## Deliverables

**Files created (15):**

```
en1gma/execution/ib/__init__.py
en1gma/execution/ib/config.py
en1gma/execution/ib/orders.py
en1gma/execution/ib/positions.py
en1gma/execution/ib/account.py
en1gma/execution/ib/real_client.py
en1gma/execution/ib/paper_adapter.py
en1gma/scripts/drills/__init__.py
en1gma/scripts/drills/ib_paper_validation.py
en1gma/scripts/drills/ib_paper_roundtrip.py
en1gma/tests/unit/test_ib_paper_adapter.py
en1gma/tests/unit/test_ib_config.py
en1gma/tests/contract/test_ib_paper_adapter_protocol.py
en1gma/tests/integration/test_ib_paper_roundtrip.py
.env.example
```

**Files modified (2):** `pyproject.toml`, `en1gma/execution/broker_factory.py`

**Commits expected:** 7

**Test count delta:** +11 unit/contract (697 → 708 baseline) + 2 integration (env-gated, default SKIPPED) + 1 SW19 Sunday-flake unchanged.

---

## Exit Gates

| Gate | Criterion |
|---|---|
| **G1** DEP_INSTALLED | `ib_insync` importable; `en1gma/execution/ib/` package in place |
| **G2** IB_ISOLATION | `grep -rn 'from ib_insync' en1gma/` → exactly 1 hit (`real_client.py`) |
| **G3** PROTOCOL_SATISFIED | `IBPaperAdapter` satisfies `BrokerAdapter` Protocol via runtime isinstance (TI08) |
| **G4** FACTORY_DISPATCH | `build_broker(PAPER)` → `IBPaperAdapter`; SHADOW/TEST → `PaperBroker`; LIVE → `NotImplementedError` (TI09-11 + existing TB05) |
| **G5** DRILL_PASS_VS_LIVE_GATEWAY | Both drill scripts PASS when run manually against G's Gateway. Verbatim output captured in T6 commit message. |
| **G6** INTEGRATION_PASS_GATED | TI12 + TI13 PASS with `IBKR_INTEGRATION_TEST=1` + Gateway. SKIP cleanly without env var. |
| **G7** DEFAULT_SUITE_GREEN | pytest full suite (no IB env vars) — 708 unit/contract PASS + 2 integration SKIPPED + 1 SW19 flake. Zero regressions. |
| **G8** PAPER_MODE_LIVE_OBSERVATION | Post-T5 first ARS session in PAPER mode executes against real IB paper account end-to-end. G observes manually. Discrepancies → rollback T5. |

---

## Invariants

### Registered

| Invariant | Statement |
|---|---|
| `INV-IBKR-PAPER-GUARD-1` | LIVE mode requires `IBKR_ALLOW_LIVE=true` + restart. Default config refuses LIVE. en1gma additionally enforces via governance `NotImplementedError` until T2 ceremony contract ships. |
| `INV-IBKR-ACCOUNT-CHECK-1` | Every IB connection validates `account_id` prefix: `DU*` for PAPER, `U*` for LIVE. Mismatch raises before any order submit. |
| `INV-IBKR-CONFIG-1` | IBKR credentials, account IDs, live-enable flags NEVER hardcoded — only from environment via `IBKRConfig.from_env`. `.env.example` documents the contract; real `.env` gitignored. |
| `INV-IBKR-CLIENT-ISOLATION` | `ib_insync` imported in exactly one file: `en1gma/execution/ib/real_client.py`. All other code interacts via `IBPaperAdapter` (Protocol) or typed dataclasses. Keeps `ib_insync` swappable. |
| `INV-IBKR-PAPER-PORT-CONTRACT` | Port 4002 reserved for PAPER, 4001 for LIVE. `IBKRConfig._set_mode_defaults` enforces port-mode consistency. |
| `INV-IBKR-CLIENT-ID-ALLOCATION` | `clientId` allocated per process role: **1=River** (future), **2=Broker** (en1gma `IBPaperAdapter`/`IBLiveAdapter`), **3=COO** (future). Drills use 99. |

### Preserved

- `INV-GOV-HALT-BEFORE-ACTION` — `IBPaperAdapter` halt-checks before connect/submit
- `INV-BROKER-PROTOCOL-IS-CONTRACT` — `IBPaperAdapter` satisfies the Protocol
- `INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE`
- `INV-PAPER-GOVERNANCE-PARITY-WITH-LIVE` — operationally **strengthened**: PAPER now uses real broker plumbing
- `INV-MODE-EXPLICIT-PER-INVOCATION`
- `INV-REPLAY-DETERMINISM` — replay uses TEST/SHADOW (still PaperBroker)

---

## Follow-ups — The Brief Chain This Unblocks

### `MODULE.IB_LIVE_ADAPTER`
`IBLiveAdapter` mirrors `IBPaperAdapter` against IB LIVE account (port 4001). T2 ceremony contract required.
**Prerequisites:** this brief + `T2_CEREMONY_CONTRACT`

### `MODULE.IB_CONNECTION_SUPERVISOR`
Lift phoenix `supervisor.py` (398L) + IBC plist activation + clientId allocator + auto-reconnect with escalation. Adds resilience.
**Prerequisites:** this brief

### `MODULE.IB_BRACKET_ORDERS`
Native broker-held SL+TP. Eliminates bar-by-bar Python SL/TP monitoring risk (if daemon crashes mid-trade, live SL is gone).
**Prerequisites:** this brief + `MODULE.POSITION_LIFECYCLE_EXTENSION`

### `MODULE.POSITION_LIFECYCLE_EXTENSION`
Extend `Position` FSM with `SUBMITTED` / `ACKED` / `PARTIAL_FILL` states for async IB lifecycle.
**Prerequisites:** this brief

### `MODULE.IB_DEGRADATION`
Lift phoenix `degradation.py` (301L). Graceful fallback when IB misbehaves.
**Prerequisites:** `MODULE.IB_CONNECTION_SUPERVISOR`

### `MODULE.SENTINEL_LIVENESS_UPGRADE`
Replace TCP check with API roundtrip. Independent track — can land before or after.

### `MODULE.IBC_LIFECYCLE_SUPERVISOR`
Wire `/Users/a8ra_m3/ibc/local.ibc-gateway.plist` into launchd for auto-relogin after daily Gateway restart.
**Prerequisites:** `MODULE.IB_CONNECTION_SUPERVISOR`

### `MODULE.RIVER_IBKR_STREAMER`
Lift `phoenix/river/streamer.py` `reqHistoricalData` streaming into en1gma. Uses `clientId=1`. **G called the river pipeline out explicitly in the kickoff message — this is the bar-ingest companion brief to the broker chain.**
**Prerequisites:** this brief + `MODULE.IB_CONNECTION_SUPERVISOR`

---

## Notes for Opus

- **LIFT-AND-RESHAPE, not write-from-scratch.** Phoenix files are PROVEN — passed S33 Phase 1 exit gate with real IB Gateway round-trips. Treat as source-of-truth for behaviour. Your job: extract lean core, strip phoenix machinery (beads, phoenix T2 store, reconnect machine), rewire to en1gma idioms (decision_trace, notification queue, en1gma `OperatingMode`, en1gma halt/lease/risk).
- Simplify aggressively where phoenix code diverges from kernel idiom. Kernel does not need phoenix's full observability surface.
- **DO NOT lift** `mock_client.py` — `PaperBroker` supersedes.
- **DO NOT lift** `session_bead.py` — decision_trace + notification queue suffice.
- **DO NOT lift** `supervisor.py` / `degradation.py` / `heartbeat.py` — deferred. First integration is intentionally minimal (connect, submit, fill, disconnect). G runs Gateway manually today; acceptable for first PAPER cycle.
- **Synchronous fill wrapper:** phoenix drill uses `time.sleep(3)`. Sloppy for production. In `IBPaperAdapter`, use `ib_insync` `Trade.fillEvent` (or poll `trade.orderStatus.status == 'Filled'` with timeout). Default 30s. Configurable via `IBKRConfig.fill_timeout_sec`.
- **Type collision:** phoenix `Order`/`OrderResult`/`Position` collide with en1gma's existing `OrderResult` (broker_protocol) and `Position` (execution/position). Rename phoenix imports to IB-prefixed: `IBOrder`, `IBOrderResult`, `IBOrderStatus`, `IBPosition`, `IBPositionSnapshot`. en1gma's existing symbols stay as-is.
- **Factory laziness:** import `IBPaperAdapter` LAZILY inside PAPER branch. TEST/SHADOW callers must not pay `ib_insync` import cost (and unit tests should not require Gateway to run).
- **Activation discipline:** T5 is the only commit that activates IB. Treat as a deployment gate. Run activation_protocol checklist before merging. Be prepared to git-revert T5 alone if first live observation surfaces issues.
- **Drills are scripts, not tests.** Place under `en1gma/scripts/drills/`. Manual invocation: `python -m en1gma.scripts.drills.ib_paper_validation`. Capture verbatim output in T6 commit.
- **Integration tests env-gated** with `@pytest.mark.integration` + skip-unless-env. Default pytest on a developer machine MUST NOT require Gateway. CI continues unit/contract only.

---

## Dependencies + Rollback

**Upstream:** `MODULE.BROKER_ADAPTER` (Protocol + factory must ship first), SW08 (already shipped)

**Blocks:** `MODULE.IB_LIVE_ADAPTER`, `MODULE.IB_CONNECTION_SUPERVISOR`, `MODULE.IB_BRACKET_ORDERS`, `MODULE.IB_DEGRADATION`, `MODULE.IBC_LIFECYCLE_SUPERVISOR`, `MODULE.RIVER_IBKR_STREAMER`

**Rollback strategy:**
- **PARTIAL (primary):** revert T5 only (factory PAPER branch). Restores `PaperBroker` for PAPER. T1-T4 + T6-T7 stay landed (IB surface dormant). Zero data risk.
- **FULL (secondary):** revert all 7 commits in reverse order. Requires removing `ib_insync` from `pyproject.toml`.

**Risk:**
- T1-T4 + T6-T7 additive — **LOW**
- T5 changes meaning of PAPER mode — **MEDIUM**. Mitigated by: (a) drill scripts proving the IB path before T5, (b) T5 as single-commit change, (c) activation_protocol checklist, (d) first PAPER session post-T5 observed manually by G.

---

*Canonical YAML source: `docs/briefs/BRIEF.MODULE.IB_PAPER_ADAPTER.yaml`*
