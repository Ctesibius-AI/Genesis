"""genesys-backfill — batch backfill injection door (CLI).

Usage:
    genesys-backfill <paths...> [--data DIR] [--dry-run]

Feeds historical Claude Code .jsonl session transcripts through the EXISTING
capture pipeline (genesys.hooks.adapter.dispatch, SessionEnd path) to enqueue them
for later extraction. THIN DRIVER: no new transcript parsing — dispatch already
reads the jsonl, translates, mirrors (capture+scrub), and calls fast_path_save.

Key behaviours:
  - Chronological order: sessions are processed by content start time (min record
    timestamp), falling back to file mtime. This ordering is load-bearing for the
    bi-temporal baseline.
  - Injected clock: each session is dispatched with now=<its own END timestamp>, so
    episodes land at the session's own time, NOT wall-clock.
  - Idempotency: the ledger has NO native dedup on session_id / source_transcript_ref
    (fast_path_save always mints a fresh episode id and appends). So this driver adds
    a guard: it scans existing ledger entries (links.session_id) and skips sessions
    already enqueued. Re-running the same batch enqueues 0.
  - --dry-run prints the ordered plan and writes NOTHING.
  - Robust: reuses the tolerant jsonl reader; one malformed/empty session never
    crashes the batch.

OFFLINE: SessionEnd dispatch is model-free (no backend needed). No network, no LLM.
This CLI does NOT drain/extract — that is genesys.extraction.live.run_once, a
separate step.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from genesys.backfill.discover import SessionPlan, build_plan
from genesys.hooks.adapter import dispatch
from genesys.ledger.store import read_all

DEFAULT_DATA = Path("~/.genesys/data").expanduser()


def _existing_session_ids(data_root: Path) -> set[str]:
    """Session ids already present in the ledger (idempotency guard).

    The ledger keys entries by minted episode id, not session_id; the session_id
    lives in links.session_id. There is no native dedup, so we build the set here.
    """
    ids: set[str] = set()
    for entry in read_all(data_root):
        sid = entry.links.session_id
        if sid:
            ids.add(sid)
    return ids


def _inject_now(plan: SessionPlan) -> str:
    """Resolve the clock to inject for a session: its END timestamp, else mtime ISO.

    An empty session (no records / no timestamps) has no content end; fall back to
    the file-mtime-derived sort key so downstream ledger month/date slicing works.
    """
    if plan.end_ts:
        return plan.end_ts
    return plan.sort_key.isoformat()


def _span(plan: SessionPlan) -> str:
    start = plan.start_ts or "?"
    end = plan.end_ts or "?"
    return f"{start} → {end}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesys-backfill",
        description="Backfill historical Claude Code .jsonl transcripts into the "
                    "Genesys capture queue (enqueue only; no extraction).",
    )
    parser.add_argument(
        "paths", nargs="+",
        help=".jsonl files and/or directories (directories are recursed for *.jsonl).",
    )
    parser.add_argument(
        "--data", default=str(DEFAULT_DATA),
        help="Data root (default: ~/.genesys/data).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the ordered plan and write NOTHING.",
    )
    parser.add_argument(
        "--wal", action="store_true",
        help="Use the F5 WAL path: append the delta to the rolling record + annotate a "
             "window, instead of copying an episode (§2.1/§2.2, unifies with the live path).",
    )
    args = parser.parse_args(argv)

    data_root = Path(args.data).expanduser()
    plans = build_plan(args.paths)

    if not plans:
        print("no .jsonl sessions found in the given paths.")
        return 0

    # ------------------------------------------------------------------ #
    # Dry-run: print the ordered plan, write nothing.                     #
    # ------------------------------------------------------------------ #
    if args.dry_run:
        print(f"[dry-run] {len(plans)} session(s) in chronological order:")
        for i, plan in enumerate(plans, 1):
            print(
                f"  {i}. {plan.session_id}  "
                f"events={plan.event_count}  "
                f"ts=[{_span(plan)}]  "
                f"→ would enqueue (now={_inject_now(plan)})"
            )
        print(f"[dry-run] 0 enqueued, 0 skipped (nothing written).")
        return 0

    # ------------------------------------------------------------------ #
    # Real run: enqueue chronologically, skipping already-present ids.    #
    # ------------------------------------------------------------------ #
    already = _existing_session_ids(data_root)
    enqueued: list[str] = []
    skipped: list[str] = []

    for plan in plans:
        if plan.session_id in already:
            skipped.append(plan.session_id)
            print(f"skip   {plan.session_id}  (already enqueued)")
            continue

        hook = {
            "hook_event_name": "SessionEnd",
            "transcript_path": str(plan.path),
            "session_id": plan.session_id,
        }
        try:
            result = dispatch(hook, data_root, now=_inject_now(plan), wal=args.wal)
        except Exception as exc:  # noqa: BLE001 — one bad session must not kill the batch
            print(f"error  {plan.session_id}  ({exc}) — skipped")
            skipped.append(plan.session_id)
            continue

        entry_id = result.get("entry_id", "?")
        enqueued.append(plan.session_id)
        already.add(plan.session_id)  # guard within this batch too
        print(f"enqueue {plan.session_id}  → {entry_id}  (now={_inject_now(plan)})")

    print(f"\n{len(enqueued)} enqueued, {len(skipped)} skipped (chronological order).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
