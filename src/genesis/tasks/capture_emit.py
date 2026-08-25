"""P5 integration seam — capture task-lifecycle signal -> task.* events (spec §4.10, DR-37).

The DR-37 capture-mirror (``genesis.capture.mirror``) surfaces first-class
``task.created`` / ``task.completed`` projection entries at capture time (spec §4.2a):
each carries the task label (``content``) and a capture correlation id
(``meta["task_id"]``) that pairs a create with its later complete.

This module is the one open seam between that signal and the event-sourced Tasks store
(spec §4.10, DR-11/DR-17). It folds a ``CaptureResult`` into ``TaskEvent`` appends via the
existing emit API (``record_created`` / ``record_done``) — nothing more. Truth stays the
event log; the department is derived (DR-17).

Design (matches the P4 drain-wiring contract — pure, clock-injected, opt-in at call sites):
  - Reads the **memory-grade** projection (the clean one extraction consumes), where task
    entries live as ``ProjectionEntry(kind="task.created"|"task.completed")``.
  - **Deterministic store id**: the capture correlation id maps 1:1 to a store task id
    (``TS-cap-<capture_id>``). No wall-clock counter, so the same capture yields the same
    id across runs and across fresh stores — a ``task.completed`` closes exactly the task
    its ``task.created`` opened.
  - **Idempotent**: re-running the same capture never double-emits. Stop AND SessionEnd
    both mirror the same transcript (§4.2a); replaying must be a no-op. We check the
    existing event log before each append.
  - A ``task.completed`` whose id was never created (in this capture or the store) is
    ignored defensively — there is nothing to close (mirrors the projection fold's own
    orphan-tolerance).

No wall-clock here; ``ts`` is injected. No network, no LLM, no graph.
"""

from __future__ import annotations

from pathlib import Path

from genesis.capture.mirror import CaptureResult
from genesis.tasks.emit import record_created, record_done
from genesis.tasks.events import read_events


def _store_task_id(capture_id: str) -> str:
    """Deterministic store id for a capture correlation id (no wall-clock counter)."""
    return f"TS-cap-{capture_id}"


def emit_task_events_from_capture(
    data_root: Path,
    capture: CaptureResult,
    *,
    ts: str,
    source_episode: str,
    kind: str = "task",
) -> dict[str, str]:
    """Emit task.* events for every task-lifecycle entry in ``capture`` (§4.10, DR-37).

    Reads the memory-grade projection's ``task.created`` / ``task.completed`` entries and
    appends the corresponding ``task.created`` / ``task.done`` events to the store, keyed by
    a deterministic id derived from the capture correlation id. Idempotent and clock-injected.

    Args:
        data_root: Genesis data root (the tasks event log lives under ``tasks/``).
        capture: the ``CaptureResult`` from ``mirror_events`` (§4.2a).
        ts: ISO-8601 timestamp for the emitted events (clock-injected; no wall clock).
        source_episode: the ledger/episode id the events are attributed to.
        kind: task kind for created events (``"task"`` default; ``"commitment"`` for
            deadline-bearing promises — the caller decides).

    Returns:
        A map ``{capture_id: store_task_id}`` of the created tasks this call is responsible
        for (empty if there was no task-lifecycle signal). Deterministic and stable across
        idempotent re-runs.
    """
    entries = capture.memory_grade.entries

    # What is already in the store, so a replay is a no-op (idempotency, §4.2a Stop+End).
    existing = read_events(data_root)
    have_created: set[str] = {e.task_id for e in existing if e.event == "task.created"}
    have_done: set[str] = {e.task_id for e in existing if e.event == "task.done"}

    created: dict[str, str] = {}

    for entry in entries:
        capture_id = entry.meta.get("task_id")
        if not capture_id:
            continue  # a task entry with no correlation id can't be paired — skip.
        store_id = _store_task_id(capture_id)

        if entry.kind == "task.created":
            if store_id not in have_created:
                record_created(
                    data_root,
                    ts=ts,
                    source_episode=source_episode,
                    title=entry.content,
                    kind=kind,
                    task_id=store_id,
                )
                have_created.add(store_id)
            created[capture_id] = store_id

        elif entry.kind == "task.completed":
            # Only close a task that exists (created earlier in this capture, or already in
            # the store). An orphan completion has nothing to close (defensive, DR-17 fold).
            if store_id not in have_created:
                continue
            if store_id not in have_done:
                record_done(
                    data_root, ts=ts, task_id=store_id, source_episode=source_episode
                )
                have_done.add(store_id)

    return created
