# BRIEF.MODULE.COO_OPERATOR_SURFACE

| | |
|---|---|
| **Mission** | MAKE_THE_RAIL_OPERABLE_FROM_COO |
| **Owner** | Opus (Cursor) |
| **Format** | LEAN (first in new format) |
| **Date** | 2026-05-25 |
| **Series** | `BRIEF.MODULE.*` — fifth brief |
| **Repo** | `SlimWojak/execution` |

---

## Mission

The rail is built; COO needs to operate it. Today every operational action (grant a mode, inspect runtime, audit a grant) requires opening a Python REPL or constructing test fixtures by hand. This brief adds the CLI verbs COO will actually use, prepends the grant step into the IB Gateway runbook (so `assert_mode_granted` doesn't surprise operators), and bundles the 2 polish nitpicks from the 4b539b9 review.

**Net:** rail becomes operable from `python run.py` alone, with audit trail visible in the same surface.

---

## Context

**Status in:** post-4b539b9 — all 7 review PRs landed, `mode_promotion.py` shipped, `inspect.py` shipped, 6 new test files green.

**Out of scope:**
- MCP server wrapping (CLI today; verb mapping follows once verb list is locked)
- Telegram digest of inspect (defer; ssh + CLI suffices)
- Grant revocation / TTL (LIVE adapter territory; PAPER grants forever per MVP)
- Multi-process grant lock (single-machine assumption — document, don't engineer)

---

## Sprawl Audit

**Exists:** `mode_promotion.py` (grant/list/assert + JSONL + env override), `inspect.py` (passive runtime aggregator), `run.py` (5 existing flags), runbooks for IB Gateway + River.

**Missing:**
- Grant CLI — operators must drop into Python to record a grant
- Inspect CLI — no one-liner to print rail state
- List-grants CLI — no JSONL audit without manual `cat`
- Runbook prepend — `IB_GATEWAY_OPERATIONS` Phase 2 (broker validation) builds PAPER adapter, which raises `ModePromotionError` unless grant has been recorded first

**Polish nitpicks bundled:**
1. `broker_adapter.py:74,80` — `PaperBroker.close_position` body returns `ExitResult(...)` while annotation says `-> CloseFillEvent`. Semantically equivalent via alias, inconsistent. Change body to `CloseFillEvent`.
2. `mode_promotion.py` — module docstring silent on single-machine concurrency assumption. Add one sentence: JSONL append per-process-atomic only.

---

## Target Shape

### `run.py` new flags

| Flag | Behaviour |
|---|---|
| `--grant-mode {SHADOW,PAPER}` | calls `grant_mode(...)`. Requires `--reason` + `--grantor`. LIVE rejected by argparse choices. |
| `--reason <str>` | free-form; recorded in grant record |
| `--grantor <str>` | free-form; recorded in grant record |
| `--list-grants [--mode M]` | tails grants JSONL (last 10). Optional mode filter. |
| `--inspect` | calls `inspect_runtime()` with no live refs (gateway-only); prints JSON. Exit 0 if gateway reachable, 1 if not. |

Future `--inspect` extension: when COO has live refs to a running adapter/supervisor/streamer (via a snapshot file), reads those too. Snapshot file = separate follow-up brief.

### Runbook updates

`IB_GATEWAY_OPERATIONS.md` — insert before existing Phase 2:

```markdown
## Phase 1.5 — Grant PAPER mode (required before broker build)
python run.py --grant-mode PAPER --reason "initial paper cutover" --grantor "<your name>"
python run.py --list-grants --mode PAPER     # confirm written
```

Without this grant, `build_broker(PAPER, ...)` raises `ModePromotionError`. Factory enforces regardless of caller — no bypass. `INV-MODE-PROMOTION-REQUIRED`.

`RIVER_OPERATIONS.md` Phase 3 preamble — note: River does NOT require a mode grant (River is observation, not capital action). Grants apply to broker rail only.

`README.md` Quick reference — append the three new CLI calls.

---

## Task Sequence

### T1 — Grant CLI
**Files:** `run.py`
- argparse: add `--grant-mode` (choices=[SHADOW,PAPER]), `--reason`, `--grantor`, `--list-grants`, `--inspect`
- `cmd_grant_mode`: validate reason+grantor non-empty; call `grant_mode`; print record; exit 0
- `cmd_list_grants`: read JSONL; optional mode filter; print last 10; exit 0
- `cmd_inspect`: call `inspect_runtime(include_gateway=True)`; `json.dumps` to stdout; exit code from `gateway_reachable.passed`

**Commit:** `feat(COO): grant + list-grants + inspect CLI verbs on run.py (T1)`
**Verify:** `python run.py --grant-mode PAPER --reason test --grantor opus` → writes record; `python run.py --list-grants` → shows it; `python run.py --inspect` → JSON with `gateway_reachable` block

### T2 — Polish
**Files:** `execution_rail/broker_adapter.py`, `execution_rail/mode_promotion.py`
- PaperBroker `close_position`: 2× `ExitResult(...)` → `CloseFillEvent(...)`
- `mode_promotion.py` docstring: add concurrency-assumption sentence

**Commit:** `chore(COO): align PaperBroker return naming + document mode_promotion concurrency assumption (T2)`
**Verify:** `grep ExitResult execution_rail/broker_adapter.py` → only import remains; pytest green

### T3 — Runbooks
**Files:** `docs/runbooks/IB_GATEWAY_OPERATIONS.md`, `docs/runbooks/RIVER_OPERATIONS.md`, `README.md`
- IB_GATEWAY_OPERATIONS — insert Phase 1.5 before Phase 2
- RIVER_OPERATIONS — Phase 3 preamble note on no-grant-needed
- README — Quick reference CLI append

**Commit:** `docs(COO): runbook prepends grant step + README CLI quick-ref (T3)`
**Verify:** read each runbook top-to-bottom; grant step appears before any code path that hits `assert_mode_granted`

### T4 — Tests

| ID | Assertion |
|---|---|
| TC01 | `--grant-mode PAPER --reason X --grantor Y` writes to env-overridden ledger; exit 0; stdout contains 'PAPER' |
| TC02 | `--grant-mode LIVE` → argparse rejects (choices guard); exit non-zero |
| TC03 | `--grant-mode PAPER` without `--reason` → argparse rejects; exit non-zero |
| TC04 | `--list-grants` on empty ledger → exit 0; stdout 'no grants recorded' |
| TC05 | `--list-grants` after T1+grant → exit 0; stdout contains record |
| TC06 | `--list-grants --mode SHADOW` after PAPER-only grants → empty/no-records |
| TC07 | `--inspect` with Gateway up → exit 0; stdout parses as JSON; `gateway_reachable.passed` true |
| TC08 | `--inspect` with Gateway down → exit 1; stdout parses as JSON; `gateway_reachable.passed` false |

**Files:** `tests/unit/test_run_cli_grant.py`, `test_run_cli_list_grants.py`, `test_run_cli_inspect.py`
**Commit:** `test(COO): CLI verb suite for grant/list-grants/inspect (T4)`

---

## Invariants

**Registered:** `INV-MODE-PROMOTION-REQUIRED` — any code path constructing a real broker adapter (IBPaperAdapter today, IBLiveAdapter future) MUST pass through `assert_mode_granted`. No bypass. The grant CLI is the sole operator surface for writing grants; factory + session enforce on read.

**Preserved:** `INV-BROKER-PROTOCOL-IS-CONTRACT`, `INV-BROKER-FACTORY-SINGLE-CONSTRUCTION-SITE`, `INV-IBKR-CLIENT-ISOLATION` (`run.py` adds no `ib_insync` import).

---

## Follow-ups

- `MODULE.RAIL_SNAPSHOT_FILE` — supervisor + adapter + streamer write periodic JSON snapshot to `~/execution/state/snapshot.json`; `--inspect` reads it; lets COO inspect a running daemon without process-attach
- `MODULE.MCP_VERB_WRAPPER` — wrap `grant_mode` + `inspect_runtime` as MCP verbs (covers `promote_mode` partial + `inspect[target=runtime]` from candidate_C's 11)
- `MODULE.EXTRACTION_FIDELITY_PROBE` — one-off Opus/GPT diff `phoenix/river/streamer.py` vs `execution_rail/river/streamer.py`; validates Composer lift model
- `MODULE.GRADUATION_CEREMONY_CONTRACT` — formal SHADOW→PAPER→LIVE multi-factor gate; extends `mode_promotion` with TTL + multi-grantor + ceremony evidence

---

## Rollback

Revert T1+T4 to remove CLI + tests. T2+T3 are docstring/runbook only — harmless to keep. CLI additions are additive; no existing flag behaviour changes.

---

*Canonical YAML: `docs/briefs/BRIEF.MODULE.COO_OPERATOR_SURFACE.yaml`*
