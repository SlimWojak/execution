# Brief 4 prep — MODULE.RIVER_IBKR_STREAMER

**Status:** SHIPPED (v0.4.0) — superseded by implementation.

This prep note captured pre-authoring decisions. The shipped module lives at `execution_rail/river/`.

## Resolved decisions

| Open question (prep) | Resolution |
|---------------------|------------|
| Second `ib_insync` importer? | Yes — intentional. 3 import sites: `real_client.py`, `streamer.py`, `writer.py`. Different IB API surfaces; not coupled through one wrapper. |
| Target shape | Full lift: schema, synthetic, writer, streamer, seam, supervisor, resubscribe — not the minimal 3-file sketch. |
| en1gma vs execution | Implemented in `~/execution` per candidate_C EXECUTION slot. en1gma thin-import wiring remains a followup. |

## Where to look

- Architecture + prod activation: `README.md`
- Current status: `STATUS.md`
- Authoritative brief: `BRIEF.MODULE.RIVER_IBKR_STREAMER.md`
- Operations: `docs/runbooks/RIVER_OPERATIONS.md`
