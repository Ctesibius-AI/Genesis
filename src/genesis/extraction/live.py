"""Live drain wiring — real graph engine, LLM backend, and embedder scorer (spec §4.14, DR-05c, §8).

All heavy imports (graphiti-core, anthropic, fastembed) are lazy — this module is safe to import
in the offline test suite. The offline suite never calls build_live / run_once / run_forever so the
lazy-only contract holds. Wall-clock is only used in run_forever (the runner boundary), not inside
drain_once itself, preserving testability.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from genesis.graph.client import PersistenceError  # offline-safe (no graphiti import)

DATA_ROOT_DEFAULT = Path.home() / ".genesis" / "data"


# ---------------------------------------------------------------------------
# Key helpers (never print the key)
# ---------------------------------------------------------------------------

def _fetch_api_key() -> str:
    """Return the Anthropic API key from macOS Keychain. NEVER prints the key (spec §4.14)."""
    result = subprocess.run(
        ["security", "find-generic-password", "-a", "genesis", "-s", "ANTHROPIC_API_KEY", "-w"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Live component factory
# ---------------------------------------------------------------------------

def build_live(data_root: Path, *, db_path: str | None = None):
    """Build (engine, backend, scorer) wired to the real graph, LLM, and embedder (spec §4.14).

    All heavy imports (graphiti-core, anthropic, fastembed) happen lazily inside this function.
    Safe to import at module level in any environment; never call in the offline suite.

    Store path — ONE PATH LAW (graph-harness T1): `db_path` is passed straight through to
    `real_client` (default None), so `build_graphiti_client` resolves `GENESIS_DB_PATH` fail-loud
    (D-GCW-2). There is deliberately NO local `data_root/graph.db` default: it silently diverged
    from the installer/daemon store (`GENESIS_DB_PATH = stores/<wsid>/graph.db`) — the worker wrote
    one file, the daemon read another, and the first live memories evaporated. `data_root` governs
    the ledger/WAL only, never the graph store.

    Returns:
        Tuple of (GraphitiEngine, AnthropicLLMBackend, real_scorer_instance).
    """
    import anthropic  # noqa: PLC0415 — lazy: absent offline

    from genesis.graph.adapter import GraphitiEngine  # noqa: PLC0415
    from genesis.graph.factory import real_client  # noqa: PLC0415
    from genesis.linking.relatedness import real_scorer  # noqa: PLC0415
    from genesis.workers.backend import AnthropicLLMBackend  # noqa: PLC0415

    client = real_client(db_path=db_path)  # None → build_graphiti_client fail-loud-resolves GENESIS_DB_PATH

    from datetime import datetime, timezone  # noqa: PLC0415 — stdlib, always present

    def _now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    engine = GraphitiEngine(client, clock=_now_iso)
    api_key = _fetch_api_key()
    backend = AnthropicLLMBackend(anthropic.Anthropic(api_key=api_key))
    scorer = real_scorer()
    return engine, backend, scorer


# ---------------------------------------------------------------------------
# run_once — single drain pass with doctor re-queue
# ---------------------------------------------------------------------------

def run_once(data_root: Path, *, now: str, window: int = 5,
             time_budget_s: float | None = None) -> list[str]:
    """Run doctor re-queue then drain_once with live components (spec §4.14, DR-05c).

    Args:
        data_root: Path to the Genesis data directory.
        now:       ISO-8601 timestamp used as the drain clock (ts= argument).
        window:    max queued entries to drain this pass (D-GCW-5 count bound).
        time_budget_s: optional wall-clock bound (D-GCW-5); stop taking new entries past it and
                   defer the rest. Used by the bounded SessionStart drain (D-GCW-18).

    Returns:
        List of processed entry IDs.
    """
    import random  # noqa: PLC0415 — stdlib

    from genesis.doctor import doctor_requeue  # noqa: PLC0415
    from genesis.extraction.drain import drain_once  # noqa: PLC0415
    from genesis.inspection.audit import FalsePassChart  # noqa: PLC0415
    from genesis.inspection.ladder import LadderConfig  # noqa: PLC0415

    doctor_requeue(data_root)
    engine, backend, scorer = build_live(data_root)
    # SWITCH-ON (owner go-ahead 2026-08-19): live extraction runs the inspection ladder.
    # shadow=False → Tier 0 hard flags route to the Verifier (owner ruling); Screen-on-raw
    # (Sonnet) + Verifier (Opus) + 5% audit are live. The chart is fresh per pass — cross-run
    # control-chart persistence is a documented follow-up. ride_along stays "" until the
    # grapher supplies an adjacent-episode corpus (shadow of that check widens harmlessly).
    processed: list[str] = []
    try:
        processed = drain_once(
            data_root, engine, backend, ts=now, scorer=scorer,
            window=window, time_budget_s=time_budget_s,
            ladder=LadderConfig(shadow=False),
            rng=random.Random(),
            chart=FalsePassChart(),
        )
        return processed
    finally:
        # LIFECYCLE (graph-harness T2): flush + shut the embedded store down cleanly so this pass's
        # writes reach the RDB on disk. Without this the in-memory FalkorDB evaporated at process
        # exit — "processed N" with an empty store. In `finally` so a drain error still persists
        # whatever committed before it.
        try:
            engine.close()
        except PersistenceError:
            # DURABILITY FAILURE (harness-savefail): the SAVE did not reach disk, so this pass's
            # graph edges are NOT durable — but drain already marked its entries DONE. Revert them to
            # queued so the ledger AGREES with the (non-durable) store; the next ordinary worker pass
            # re-extracts them (the existing resilience path). Then RE-RAISE so the worker fails loud.
            _requeue_after_failed_persist(data_root, processed)
            raise


def _requeue_after_failed_persist(data_root: Path, processed: list[str]) -> None:
    """Revert this pass's DONE entries back to queued after a failed store SAVE (harness-savefail).

    Restores ledger↔store crash-consistency: if the edges did not persist, the entries must not stay
    "done". Chosen over an "instruct the user to run a doctor requeue" message because doctor requeue
    re-queues DEAD/stuck entries, not DONE ones — so it would not actually re-queue these; reverting
    here is the simplest state where done⇔durable and queued⇔not.
    """
    if not processed:
        return
    from genesis.ledger.entry import Extracted  # noqa: PLC0415 — stdlib-cheap, keep near use
    from genesis.ledger.store import read_all, update  # noqa: PLC0415

    by_id = {e.entry_id: e for e in read_all(data_root)}
    for entry_id in processed:
        entry = by_id.get(entry_id)
        if entry is not None and entry.extracted is Extracted.DONE:
            entry.extracted = Extracted.NO
            update(data_root, entry)


# ---------------------------------------------------------------------------
# run_forever — polling loop (launchd / foreground service)
# ---------------------------------------------------------------------------

def run_forever(data_root: Path, *, interval_s: float = 10.0) -> None:
    """Drain in a loop with a real wall-clock now, sleeping interval_s between passes.

    Single-instance safety is enforced by drain_once's lockfile. This runner is the wall-clock
    boundary — run_once / drain_once themselves accept an injected ts= for testability.
    """
    from datetime import datetime, timezone  # noqa: PLC0415 — stdlib

    while True:
        now = datetime.now(tz=timezone.utc).isoformat()
        try:
            processed = run_once(data_root, now=now)
            if processed:
                print(f"[genesis-worker] drained {len(processed)}: {processed}", flush=True)
        except PersistenceError as exc:
            # Loud, but the loop survives: run_once already reverted this pass's entries to queued,
            # so the next pass re-extracts. Never a silent success (harness-savefail).
            print(f"[genesis-worker] PERSISTENCE FAILURE — store did not persist ({exc}); entries "
                  f"reverted to queued, retrying next pass.", flush=True)
        except Exception as exc:  # noqa: BLE001
            # Log to stdout/stderr (12-factor: logs as streams); never crash the loop.
            print(f"[genesis-worker] error during drain: {exc}", flush=True)
        time.sleep(interval_s)
