# BRIEF.MODULE.BROKER_ADAPTER

| | |
|---|---|
| **Mission** | BROKER_PROTOCOL_EXTRACTION + FACTORY_WIRING |
| **Owner** | Opus (Cursor / factory) |
| **Format** | DENSE |
| **Date** | 2026-05-25 |
| **Series** | First of `BRIEF.MODULE.*` — module-by-module optimisation sweep |
| **Scope** | Pure refactor. Olya-independent. No methodology surface. No new dependencies. |

---

## Mission Statement

Extract a `BrokerAdapter` Protocol from the de-facto `PaperBroker` contract, refactor `PaperBroker` to implement it, and thread an `OperatingMode → broker factory` through both orchestrator entry points.

This is the prerequisite refactor before any IB Gateway adapter (`IBPaperAdapter`, `IBLiveAdapter`) can be landed. **Zero behaviour change in this brief** — the `PaperBroker` remains the only implementation. Strategy code, governance, and decision traces remain bit-identical. The factory is the *seam* where a future `IBPaperAdapter` slots in.

---

## Context

**Status in:** clean on main, 689 tests passing + 1 SW19 Sunday-flake.

**Block state:**
- M3.5.1 Block 1 non-Olya-gated: COMPLETE (SW02/03/04/05/07/08/09)
- SW01 + SW10 remain Olya-gated
- Block 2 remediation candidates parked

**New series rationale.** G is opening a module-by-module optimisation sweep — every kernel module audited in isolation for leanness, robustness, and operational completeness. BROKER_ADAPTER is first because (a) the IB adapter is the next visible capability gap, and (b) doing the Protocol refactor BEFORE writing IB code is the cheap path — the IB PR becomes trivial once the seam exists.

**Out of scope:**
- IB Gateway integration (separate brief: `MODULE.IB_PAPER_ADAPTER`)
- Async fill lifecycle / bracket orders (depends on IB adapter)
- Connection supervisor / clientId allocator (depends on IB adapter)
- Sentinel API-roundtrip liveness upgrade (separate brief)
- Order lifecycle state machine extension (separate brief)
- Graduation ceremony / T2 token (G ruling Q3, separate contract)

---

## Sprawl Audit — Broker + IB Surface

### In-kernel (known good)

| File | Lines | Status | Verdict |
|---|---|---|---|
| `en1gma/execution/broker_adapter.py` | 110 | OPERATIONAL | **KEEP** — proven kernel PaperBroker (extracted+simplified from phoenix) |
| `en1gma/execution/position.py` | ~150 | OPERATIONAL | **KEEP** — 5-state lifecycle FSM, P&L, hash audit; sound abstraction |
| `en1gma/execution/intent_builder.py` | — | OPERATIONAL | **KEEP** — strategy chain → `BrokerIntent` translation; clean upstream of broker, no refactor needed |

### Call sites to refactor

**`en1gma/scripts/run_ars_session.py`**
- L65: `from en1gma.execution.broker_adapter import PaperBroker`
- L411: `_monitor_trade_live(..., broker: PaperBroker, ...)`
- L630: `broker = PaperBroker(halt_signal)` (live-mode path)
- L710: `broker = PaperBroker(halt_signal)` (batch-replay path)
- L711: `order = broker.open_position(symbol=pair, direction=..., size=1.0, entry_price=...)`
- L438/L453/L479: `broker.close_position(...)` for halt/sl_hit/tp_hit

**`en1gma/control/map_orchestrator.py`**
- L31: `from ..execution.broker_adapter import PaperBroker, OrderResult`
- L272: `broker = PaperBroker(halt)`
- L545: `fill = broker.open_position(...)`

### Source repos present on disk (read-only reference)

| Path | Lines | Status | Verdict |
|---|---|---|---|
| `/Users/a8ra_m3/phoenix/execution/broker_stub.py` | 484 | ORIGIN — kernel PaperBroker descended from this | **PRUNE** — kernel lifted lean version; bloat: fidelity tracking, bead emission, RNG-driven slippage modes |
| `/Users/a8ra_m3/phoenix/drills/ibkr_paper_validation.py` | 387 | PROVEN — S33 Phase 1 IBKR paper validation | **LIFT in next brief** — connects to IB Gateway on 127.0.0.1:4002, verifies account, places test order, queries fill. References `INV-IBKR-PAPER-GUARD-1`, `INV-IBKR-ACCOUNT-CHECK-1`. |
| `/Users/a8ra_m3/phoenix/drills/ibkr_paper_trade_roundtrip.py` | 422 | PROVEN — S33 full round-trip lifecycle | **LIFT in next brief** — `CONNECT → T2_TOKEN → BUY → FILL → POSITION → SELL → CLOSE → DISCONNECT` |

### Infrastructure present, unwired

| Path | Role | Status | Verdict |
|---|---|---|---|
| `/Users/a8ra_m3/Jts/` | IBKR TWS / Gateway runtime | INSTALLED + LAUNCHING (launcher logs through 2026-05-24) | Already operational; G runs Gateway manually today |
| `/Users/a8ra_m3/ibc/` | IBController — credential-driven Gateway lifecycle | INSTALLED — start/stop/check/reconnect scripts + `local.ibc-gateway.plist` launchd unit (not activated) | Available for `MODULE.IBC_LIFECYCLE_SUPERVISOR` brief |

### Duplicate `PaperBroker` implementations

**Found: 0.** Only `en1gma/execution/broker_adapter.py` defines `PaperBroker` inside the kernel. Phoenix's `broker_stub.py` is source-repo reference, not duplicate kernel code. **No de-duplication needed in this brief.**

### Bloat to remove in this brief

**None.** The kernel `PaperBroker` is already minimal. This brief ADDS a Protocol seam; it does not remove implementation code. Bloat removal opportunities are confined to phoenix source repo (already pruned during original extraction) and are out of scope.

---

## Target Shape

### Protocol — `en1gma/execution/broker_protocol.py` (new file)

Separate file (not inside `broker_adapter.py`) so `PaperBroker` and any future `IBPaperAdapter` / `IBLiveAdapter` all import the Protocol from a single canonical location with no circular coupling to a concrete implementation.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class BrokerAdapter(Protocol):
    """Minimal contract every broker must honour."""

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        entry_price: float,
    ) -> OrderResult: ...

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "exit",
    ) -> ExitResult: ...

    def halt_all(self, halt_id: str) -> int: ...

    def get_total_pnl(self) -> dict[str, float]: ...
```

**Notes:**
- `OrderResult` + `ExitResult` dataclasses move from `broker_adapter.py` into `broker_protocol.py` (they are the contract's return shape).
- `@runtime_checkable` enables `isinstance(broker, BrokerAdapter)` for tests.
- Method signatures are EXACTLY today's `PaperBroker` — no surface drift, no new params.
- Async / bracket / lifecycle hooks are deliberately absent — those land in the IB adapter brief along with the lifecycle FSM extension.

### Factory — `en1gma/execution/broker_factory.py` (new file)

```python
from ..control.governance import OperatingMode
from ..control.halt import HaltSignal
from .broker_adapter import PaperBroker
from .broker_protocol import BrokerAdapter

def build_broker(mode: OperatingMode, halt: HaltSignal) -> BrokerAdapter:
    """
    Sole broker construction site. Today: always PaperBroker.
    Future: PAPER/LIVE modes dispatch to IBPaperAdapter /
    IBLiveAdapter once those land.
    """
    if mode in (OperatingMode.TEST, OperatingMode.SHADOW, OperatingMode.PAPER):
        return PaperBroker(halt)
    if mode == OperatingMode.LIVE:
        # Defence-in-depth — governance.validate_config already
        # raises NotImplementedError on LIVE (SW08, Q3 ruling),
        # but factory must not silently fall through.
        raise NotImplementedError(
            "LIVE broker not yet implemented; "
            "see MODULE.IB_LIVE_ADAPTER brief"
        )
    raise ValueError(f"unknown mode: {mode}")
```

**Notes:**
- Pure construction — no orchestration, no governance evaluation. `INV-ORCHESTRATOR-DUMB` spirit preserved.
- Mode parameter mirrors SW08's `INV-MODE-EXPLICIT-PER-INVOCATION` — broker construction is mode-aware from day one of the factory's existence.
- Returns `BrokerAdapter` type (Protocol), not `PaperBroker` concrete type — call sites depend on the contract, not the implementation.

### `PaperBroker` refactor — `en1gma/execution/broker_adapter.py`

- Move `OrderResult` + `ExitResult` dataclasses → `broker_protocol.py`
- Re-import them in `broker_adapter.py` for back-compat (no breakage at import boundary)
- `PaperBroker` class body unchanged — already satisfies the Protocol shape
- Add docstring noting: *"satisfies BrokerAdapter Protocol (broker_protocol.py)"*

**Behaviour delta: ZERO.**

### Call-site migration pattern

```diff
- broker = PaperBroker(halt)
+ broker = build_broker(mode, halt)   # type: BrokerAdapter

- def _monitor_trade_live(..., broker: PaperBroker, ...)
+ def _monitor_trade_live(..., broker: BrokerAdapter, ...)

- from ..execution.broker_adapter import PaperBroker, OrderResult
+ from ..execution.broker_factory import build_broker
+ from ..execution.broker_protocol import BrokerAdapter, OrderResult
```

No call site should mention `PaperBroker` by name after this brief — that is the seam that lets the IB adapter land without touching strategy code. Remaining `PaperBroker` references after the brief: (a) `broker_adapter.py` (definition), (b) `broker_factory.py` (construction), (c) tests that specifically assert `PaperBroker` semantics.

---

## Task Sequence

Order chosen for linearity: **protocol → factory → call sites → tests.** Each commit leaves the suite green.

### T1 — Protocol File (CRITICAL)
- **Files created:** `en1gma/execution/broker_protocol.py`
- **Files modified:** `en1gma/execution/broker_adapter.py`
- **Changes:**
  - Create `broker_protocol.py` with `BrokerAdapter` Protocol + `OrderResult` + `ExitResult`
  - Remove `OrderResult` + `ExitResult` definitions from `broker_adapter.py`
  - `broker_adapter.py` imports them from `broker_protocol` (preserves existing public import surface)
  - Add `@runtime_checkable` decorator
- **Atomicity:** definition only — no factory, no call-site changes.
- **Commit:** `feat(BROKER): extract BrokerAdapter Protocol + relocate result dataclasses (T1)`
- **Verification:** pytest green · `isinstance(PaperBroker(halt), BrokerAdapter) is True` · existing imports still work

### T2 — Factory File (CRITICAL)
- **Files created:** `en1gma/execution/broker_factory.py`
- **Changes:** `build_broker(mode, halt) → BrokerAdapter` dispatch on `OperatingMode`. PAPER/SHADOW/TEST → `PaperBroker`. LIVE → `NotImplementedError`. Unknown mode → `ValueError`.
- **Atomicity:** factory only — no call-site migration.
- **Commit:** `feat(BROKER): build_broker factory keyed on OperatingMode (T2)`
- **Verification:** pytest green · clean imports (no circular coupling to governance)

### T3 — Call Site Path A (CRITICAL)
- **Files modified:** `en1gma/scripts/run_ars_session.py`
- **Changes:**
  - Replace `from ...broker_adapter import PaperBroker` → factory + protocol imports
  - Both `PaperBroker(halt_signal)` construction sites (live L630, batch L710) become `build_broker(mode, halt_signal)`
  - `broker: PaperBroker` type annotation in `_monitor_trade_live` (L411) → `broker: BrokerAdapter`
  - `mode` parameter already plumbed by SW08 — no new threading needed
- **Commit:** `refactor(BROKER): Path A (ARS) consumes BrokerAdapter via factory (T3)`
- **Verification:** pytest green · `grep PaperBroker en1gma/scripts/run_ars_session.py` → zero matches · sample-session `decision_trace` bit-identical

### T4 — Call Site Path B (CRITICAL)
- **Files modified:** `en1gma/control/map_orchestrator.py`
- **Changes:**
  - Replace `from ..execution.broker_adapter import PaperBroker, OrderResult` → factory + protocol imports
  - `PaperBroker(halt)` at L272 → `build_broker(mode, halt)`
  - `mode` parameter already plumbed by SW08 — no new threading needed
- **Commit:** `refactor(BROKER): Path B (Map) consumes BrokerAdapter via factory (T4)`
- **Verification:** pytest green · `grep PaperBroker en1gma/control/map_orchestrator.py` → zero matches · 6/6 EXPANSION ground truth resolves identically

### T5 — Protocol Tests (REQUIRED)
- **Files created:** `en1gma/tests/unit/test_broker_protocol.py`
- **Cases:**

| ID | Assertion |
|---|---|
| TB01 | `isinstance(PaperBroker(halt), BrokerAdapter) is True` |
| TB02 | `build_broker(PAPER, halt)` returns `PaperBroker` instance |
| TB03 | `build_broker(SHADOW, halt)` returns `PaperBroker` instance |
| TB04 | `build_broker(TEST, halt)` returns `PaperBroker` instance |
| TB05 | `build_broker(LIVE, halt)` raises `NotImplementedError` |
| TB06 | Return-type annotation of `build_broker` is `BrokerAdapter` (introspection) |
| TB07 | `OrderResult`, `ExitResult` importable from both `broker_adapter` and `broker_protocol` with identical identity |
| TB08 | Tiny in-test `DummyBroker` with 4 Protocol methods passes `isinstance` check — proves third-party plug-in path |

- **Commit:** `test(BROKER): BrokerAdapter Protocol + factory unit suite (T5)`

---

## Deliverables

**Files created (3):**
- `en1gma/execution/broker_protocol.py`
- `en1gma/execution/broker_factory.py`
- `en1gma/tests/unit/test_broker_protocol.py`

**Files modified (3):**
- `en1gma/execution/broker_adapter.py`
- `en1gma/scripts/run_ars_session.py`
- `en1gma/control/map_orchestrator.py`

**Files deleted:** none.

**Commits expected:** 5 (T1 protocol + T2 factory + T3 Path A + T4 Path B + T5 tests)

**Test count delta:** +8 unit cases (689 → 697 baseline; +1 SW19 Sunday-flake unchanged)

---

## Exit Gates

| Gate | Criterion | Test | Binary |
|---|---|---|---|
| **G1** PROTOCOL_LANDED | `BrokerAdapter` Protocol exists; `PaperBroker` satisfies it (runtime isinstance) | `test_broker_protocol.py::TB01` | PASS\|FAIL |
| **G2** FACTORY_LANDED | `build_broker` dispatches by `OperatingMode`; LIVE raises `NotImplementedError` | TB02-TB05 | PASS\|FAIL |
| **G3** CALL_SITE_CLEAN_ARS | `grep PaperBroker en1gma/scripts/run_ars_session.py` returns zero matches | shell grep + pytest scenario | PASS\|FAIL |
| **G4** CALL_SITE_CLEAN_MAP | `grep PaperBroker en1gma/control/map_orchestrator.py` returns zero matches | shell grep + pytest scenario | PASS\|FAIL |
| **G5** ZERO_BEHAVIOUR_CHANGE | 6/6 EXPANSION ground truth byte-identical `decision_trace` + `map_timeline` vs pre-brief baseline. ARS 151/151 parity preserved (sanity-run a sample session). | scenario suite + sample session replay diff | PASS\|FAIL |
| **G6** FULL_SUITE_GREEN | pytest full suite — 697 pass + 1 SW19 Sunday-flake. Zero regressions. Zero new skips. | pytest | PASS\|FAIL |

---

## Invariants

### Registered

**`INV-BROKER-PROTOCOL-IS-CONTRACT`**
> `BrokerAdapter` Protocol in `broker_protocol.py` is the sole broker contract. Every broker implementation (`PaperBroker`, future `IBPaperAdapter`, `IBLiveAdapter`) must satisfy it via runtime isinstance check. Strategy code and orchestrators depend on the Protocol type, never a concrete class.

*Enforced by:* T5 TB01 + grep-verified absence of `PaperBroker` in call sites.

**`INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE`**
> `build_broker` in `broker_factory.py` is the sole broker construction function. No call site instantiates a broker class directly. Mirrors `INV-GOVERNANCE-SINGLE-CHECK-SITE` from SW08 — one seam, one place to evolve.

*Enforced by:* T5 TB07 + grep-verified absence of direct `PaperBroker()` calls outside `broker_adapter.py` + `broker_factory.py` + tests.

### Preserved

- `INV-GOV-HALT-BEFORE-ACTION` — `PaperBroker._check_halt` unchanged
- `INV-EXEC-LIFECYCLE-1` — `Position` state machine untouched
- `INV-ORCHESTRATOR-DUMB` — factory is dumb construction; no logic
- `INV-MODE-EXPLICIT-PER-INVOCATION` — factory consumes mode; never defaults
- `INV-REPLAY-DETERMINISM` — zero behaviour change → byte-identical replays

---

## Follow-ups — The Brief Chain This Unblocks

### `MODULE.IB_PAPER_ADAPTER`
Lift the proven IB connectivity surface from phoenix drills (`ibkr_paper_validation.py` + `ibkr_paper_trade_roundtrip.py`) into `en1gma/execution/ib_paper_adapter.py`. Implements `BrokerAdapter` Protocol against `ib_insync` + real IB paper account (port 4002, DU* accounts).

- **Prerequisites:** this brief shipped · `ib_insync` added to `pyproject.toml` · IBC config validated
- **Delta from PaperBroker:**
  - Async fill lifecycle (`open_position` returns `OrderHandle`, fill via callback) — OR synchronous wrapper that blocks on fill event with timeout (simpler intermediate)
  - Bracket order support for SL+TP at broker (not bar-by-bar in Python)
  - Connection establishment + clientId allocator
  - Disconnect handling → `halt.signal_local`

### `MODULE.IB_LIVE_ADAPTER`
`IBLiveAdapter` — live account port 4001. Gated behind T2 graduation ceremony (G ruling Q3, separate contract).
- **Prerequisites:** `MODULE.IB_PAPER_ADAPTER`, `T2_CEREMONY_CONTRACT`

### `MODULE.SENTINEL_LIVENESS_UPGRADE`
Replace TCP-reachability check in `sentinel.py:124-147` with API round-trip (`reqAccountSummary` or similar). Today's check green-lights non-functional gateways (logged out, read-only mode, etc.).
- **Prerequisites:** `MODULE.IB_PAPER_ADAPTER`

### `MODULE.IBC_LIFECYCLE_SUPERVISOR`
Wire `/Users/a8ra_m3/ibc/local.ibc-gateway.plist` into launchd so IB Gateway auto-relogs after daily restart. Today G runs Gateway manually.
- **Prerequisites:** `MODULE.IB_PAPER_ADAPTER`, `MODULE.SENTINEL_LIVENESS_UPGRADE`

### `MODULE.POSITION_LIFECYCLE_EXTENSION`
Extend `Position` FSM with submission/ack/partial-fill states to model async IB lifecycle properly. Currently `OPEN` is stamped at `PaperBroker.open_position` time as if fill were synchronous.
- **Prerequisites:** this brief

---

## Notes for Opus

- **This is a PURE REFACTOR. Behaviour change is a defect.** Every commit must show pytest green and `decision_trace` unchanged on a sanity-run sample session. If anything diverges, stop and report — don't paper over.
- **Type annotations:** prefer the Protocol (`BrokerAdapter`) over the concrete class (`PaperBroker`) at every call site after T3/T4. Concrete class is only mentioned in (a) `broker_adapter.py` definition, (b) `broker_factory.py` construction, (c) tests that specifically assert `PaperBroker` semantics.
- `@runtime_checkable` cost is not a concern at this scale (handful of broker constructions per session). Use it.
- **Do NOT** introduce an Abstract Base Class. Protocols are the right abstraction here — structural typing, no inheritance coupling, isinstance-friendly via `@runtime_checkable`.
- **Do NOT** introduce a Registry pattern (`build_broker` dispatching via a dict). YAGNI — there are 3 modes and they're enumerated. A simple if/elif on `OperatingMode` is leaner.
- SW08 already plumbs `mode: OperatingMode` through `run_ars_session` and `run_map_replay`. T3/T4 consume that existing parameter; no new threading work.
- If you discover any broker call site this brief missed, stop and report — there should only be the two listed in `sprawl_audit.call_sites_to_refactor`.

---

## Dependencies + Rollback

**Upstream dependencies:** SW08 (`OperatingMode` + mode threading)

**Blocks:** `MODULE.IB_PAPER_ADAPTER`, `MODULE.IB_LIVE_ADAPTER`, `MODULE.POSITION_LIFECYCLE_EXTENSION`

**Rollback strategy:** `git revert` the 5 commits in reverse order (T5→T1). Behaviour identical to pre-brief state.

**Risk: LOW.** Zero behaviour change, no dependency added, no migration of persisted state, no test fixture data altered. The seam is additive.

---

*Canonical YAML source: `docs/briefs/BRIEF.MODULE.BROKER_ADAPTER.yaml`*
