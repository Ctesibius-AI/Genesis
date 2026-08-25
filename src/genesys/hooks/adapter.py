"""Claude Code hook adapter — dispatch hook events to the Genesys capture pipeline.

Spec references:
  - DR-08: SessionStart injection — return diary briefing as additionalContext.
  - DR-14: Stop / SessionEnd → fast_path_save (durable); PreCompact → precompact_flush.
  - F-GENESYS-03 (provisional summary ruling): summary = last assistant_text, falling
    back to last user message, falling back to "". Documented provisional choice pending
    F-GENESYS-03 design.

NO wall-clock calls here. The ``now`` argument is clock-injected by the caller (cli.py).
NO network. Stdlib only (plus internal genesys imports).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesys.capture.mirror import mirror_events, raw_span_from_result
from genesys.config import get_assistant_name, get_principal
from genesys.diary.backend import FakeBackend
from genesys.diary.hooks import precompact_flush, session_start_context
from genesys.hooks.translate import cc_transcript_to_events, provisional_summary
from genesys.save import fast_path_save
from genesys.save_cursor import latest_span_end_for_session
from genesys.tasks.capture_emit import emit_task_events_from_capture
from genesys.wal.courier import append_and_annotate
from genesys.wal.write_cursor import read_captured_count, write_captured_count


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #

def _read_jsonl(path: str | Path) -> list[dict]:
    """Read a .jsonl file robustly: skip blank or malformed lines."""
    records: list[dict] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, IOError):
        return records
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                records.append(obj)
        except (json.JSONDecodeError, ValueError):
            continue
    return records


def _timestamps_from_events(events: list[dict]) -> tuple[str, str]:
    """Return (span_start, span_end) from events.

    Claude Code transcript records do not currently carry per-event timestamps,
    so we return ("", "") as placeholders. This assumption should be validated
    against a real Claude Code transcript.
    """
    # ASSUMPTION: CC transcript records do not carry per-event timestamps at the
    # individual record level in the current observed format. span_start and
    # span_end are left as "" until the format is confirmed.
    return "", ""


# --------------------------------------------------------------------------- #
# Public dispatch                                                               #
# --------------------------------------------------------------------------- #

def dispatch(
    hook: dict,
    data_root: Path | str,
    *,
    backend: Any = None,
    now: str,
    speakers: list[str] | None = None,
    emit_task_events: bool = False,
    cursor_delta: bool = False,
    wal: bool = False,
    annotate: bool = True,
    drain: Any = None,
) -> dict:
    """Dispatch a Claude Code hook event to the appropriate Genesys pipeline action.

    Args:
        hook: The hook payload dict (from Claude Code, delivered via stdin to cli.py).
              Expected keys vary by hook_event_name:
                - "hook_event_name": str — one of "SessionStart", "Stop", "SessionEnd",
                  "PreCompact".
                - "transcript_path": str — for Stop/SessionEnd/PreCompact hooks.
                - "session_id": str — the CC session identifier.
                - "now": str (optional) — ISO-8601 timestamp; cli.py resolves this.
        data_root: Root directory for Genesys data (ledger, episodes, diary).
        backend: DiaryBackend instance. Defaults to FakeBackend() (model-free,
                 offline). Pass None to use FakeBackend.
        now: ISO-8601 timestamp for the current moment (clock-injected from cli.py).
        speakers: List of speaker names. Defaults to the configured
            [principal, assistant] (see genesys.config).
        emit_task_events: opt-in (default OFF, backward-compatible like the P4 drain
            wiring). When True, on Stop/SessionEnd/PreCompact the capture's first-class
            task-lifecycle signal (DR-37, §4.2a) is emitted into the event-sourced Tasks
            store (§4.10, DR-17), attributed to the ledger entry the same save produced.
            Idempotent: Stop then SessionEnd over the same transcript does not double-emit.
        cursor_delta: opt-in (default OFF, backward-compatible like the P5 wiring). When True,
            Stop/SessionEnd banks only material after this session's last saved cursor; a ring
            with nothing new is skipped. Stop then SessionEnd over the same transcript does not
            double-save.
        wal: opt-in (default OFF, backward-compatible like the P5 / Plan-1 wiring). When True,
            Stop/SessionEnd/PreCompact append the delta to both rolling records and annotate the
            (cursor, now) window instead of copying an episode (§2.1/§2.2, DR-24/DR-43); n rings
            → n non-overlapping annotations (F4 dissolved).
        annotate: opt-in (default True, backward-compatible). When False and ``wal=True``, the
            WAL rings are still appended as a raw safety net but ``save_annotation`` is skipped —
            no queue item is created (append-only mode for automatic hooks). When the courier
            returns None on this path, dispatch returns ``{"appended": True, "annotated": False}``.
            Has no effect when ``wal=False`` (the legacy copy path always annotates).

    Returns:
        A dict result appropriate to the hook event type. Unknown events return {}.

    Spec: DR-08 (SessionStart), DR-14 (PreCompact), F-GENESYS-03 (provisional summary).
    """
    data_root = Path(data_root)
    if backend is None:
        backend = FakeBackend()
    if speakers is None:
        speakers = [get_principal(), get_assistant_name()]

    event = hook.get("hook_event_name", "")

    # ------------------------------------------------------------------ #
    # SessionStart — return diary briefing as additionalContext            #
    # ------------------------------------------------------------------ #
    if event == "SessionStart":
        # BT-2 / D-GCW-5: run the bounded drain BEFORE compiling the diary, so a fresh session
        # starts from an up-to-date graph. `drain` is a zero-arg callable injected by cli.py
        # (it binds the engine/backend + the count/time bound). AC-D2: a drain already in
        # progress raises LockHeld — treat it as a NO-OP and compile from current state; never
        # block or error start.
        if drain is not None:
            from genesys.extraction.lock import LockHeld
            try:
                drain()
            except LockHeld:
                pass
        # D-GCW-15 / AC-CONF1: compute the diary (LLM-only) AND the user-visible confirmation line.
        # A failed read is the DEGRADED "unavailable" path — never breaks start (AC-D2 posture).
        from genesys.hooks.confirmation import confirmation_line, memory_state
        try:
            context = session_start_context(data_root, now_iso=now, backend=backend)
            available, count = memory_state(data_root)
        except Exception:  # noqa: BLE001 — down ⇒ unavailable + empty context, start never breaks
            context, available, count = "", False, 0
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,  # LLM-only diary content (never shown to the user)
            },
            # USER-VISIBLE confirmation line (D-GCW-15 / AC-CONF1) — cli.py prints this to PLAIN
            # STDOUT (owner ruling 2026-08-26: systemMessage is model-only at SessionStart). Not part
            # of the CC hook JSON schema; the CLI pops it before emitting the structured output.
            "_confirmation_stdout": confirmation_line(available=available, count=count),
        }

    # ------------------------------------------------------------------ #
    # Stop / SessionEnd — translate transcript, mirror, fast_path_save    #
    # ------------------------------------------------------------------ #
    if event in ("Stop", "SessionEnd"):
        transcript_path = hook.get("transcript_path", "")
        session_id = hook.get("session_id", "")

        all_records = _read_jsonl(transcript_path) if transcript_path else []

        if wal and not annotate:
            # Append-only / capture-once path (Part A fix):
            # Process ONLY the new records since the last WAL append for this session.
            # The write-cursor tracks how many transcript records have been captured, so
            # each reply is appended to the WAL EXACTLY ONCE regardless of ring count.
            already_captured = read_captured_count(data_root, session_id)
            if len(all_records) < already_captured:
                # Compaction/shrink detected: the transcript was rewritten shorter than the
                # stored cursor. Re-derive from record 0 so post-compaction content is never
                # silently lost. Duplication is acceptable; loss is not.
                new_records = all_records
            else:
                new_records = all_records[already_captured:]
            if not new_records:
                return {"appended": True, "annotated": False}
            events = cc_transcript_to_events(new_records)
            capture_result = mirror_events(events)
            summary = provisional_summary(events)
            cursor = latest_span_end_for_session(data_root, session_id)
            append_and_annotate(
                data_root, capture_result=capture_result, cursor=cursor, now=now,
                session_id=session_id, speakers=speakers, jot=summary, annotate=False,
            )
            # Always update the write cursor to the full record count so the next ring
            # skips everything already captured. This also self-corrects a stale cursor.
            write_captured_count(data_root, session_id, len(all_records))
            return {"appended": True, "annotated": False}

        records = all_records
        events = cc_transcript_to_events(records)
        capture_result = mirror_events(events)

        raw_span = raw_span_from_result(capture_result)
        summary = provisional_summary(events)
        span_start, span_end = _timestamps_from_events(events)

        if wal:
            # F5 WAL path with annotation (§2.1/§2.2): append the delta to both rings +
            # annotate the (cursor, now) window. F4 dissolved structurally.
            cursor = latest_span_end_for_session(data_root, session_id)
            entry = append_and_annotate(
                data_root, capture_result=capture_result, cursor=cursor, now=now,
                session_id=session_id, speakers=speakers, jot=summary, annotate=annotate,
            )
            if entry is None:
                return {"skipped": True, "reason": "no-new-material"}
            if emit_task_events:
                emit_task_events_from_capture(
                    data_root, capture_result, ts=now, source_episode=entry.entry_id
                )
            return {"entry_id": entry.entry_id}

        entry = fast_path_save(
            data_root,
            raw_span=raw_span,
            summary=summary,
            session_id=session_id,
            speakers=speakers,
            span_start=span_start,
            span_end=span_end,
            ts=now,
            source_transcript_ref=hook.get("transcript_path", ""),
            cursor_delta=cursor_delta,
        )
        if entry is None:
            # F4-interim: nothing new for this session — skip (no task emission either).
            return {"skipped": True, "reason": "no-new-material"}
        # P5 seam (opt-in): capture task-lifecycle signal -> task.* events (§4.10, DR-37).
        if emit_task_events:
            emit_task_events_from_capture(
                data_root, capture_result, ts=now, source_episode=entry.entry_id
            )
        return {"entry_id": entry.entry_id}

    # ------------------------------------------------------------------ #
    # PreCompact — translate transcript + flush (durable + best-effort)   #
    # ------------------------------------------------------------------ #
    if event == "PreCompact":
        transcript_path = hook.get("transcript_path", "")
        session_id = hook.get("session_id", "")

        all_records = _read_jsonl(transcript_path) if transcript_path else []

        if wal and not annotate:
            # Append-only / capture-once path for PreCompact (same as Stop/SessionEnd).
            already_captured = read_captured_count(data_root, session_id)
            if len(all_records) < already_captured:
                # Compaction/shrink detected: re-derive from record 0 to avoid silent loss.
                new_records = all_records
            else:
                new_records = all_records[already_captured:]
            if not new_records:
                return {"appended": True, "annotated": False, "diary_regenerated": False}
            events = cc_transcript_to_events(new_records)
            capture_result = mirror_events(events)
            summary = provisional_summary(events)
            cursor = latest_span_end_for_session(data_root, session_id)
            append_and_annotate(
                data_root, capture_result=capture_result, cursor=cursor, now=now,
                session_id=session_id, speakers=speakers, jot=summary, annotate=False,
            )
            # Always write corrected cursor — self-heals stale count after shrink.
            write_captured_count(data_root, session_id, len(all_records))
            return {"appended": True, "annotated": False, "diary_regenerated": False}

        records = all_records
        events = cc_transcript_to_events(records)
        capture_result = mirror_events(events)

        raw_span = raw_span_from_result(capture_result)
        summary = provisional_summary(events)
        span_start, span_end = _timestamps_from_events(events)

        if wal:
            # DR-14 durability preserved as a forced final append+annotate (§5).
            cursor = latest_span_end_for_session(data_root, session_id)
            entry = append_and_annotate(
                data_root, capture_result=capture_result, cursor=cursor, now=now,
                session_id=session_id, speakers=speakers, jot=summary, annotate=annotate,
            )
            if entry is None:
                return {"entry_id": None, "diary_regenerated": False}
            if emit_task_events:
                emit_task_events_from_capture(
                    data_root, capture_result, ts=now, source_episode=entry.entry_id
                )
            return {"entry_id": entry.entry_id, "diary_regenerated": False}

        result = precompact_flush(
            data_root,
            raw_span=raw_span,
            summary=summary,
            session_id=session_id,
            speakers=speakers,
            span_start=span_start,
            span_end=span_end,
            ts=now,
            backend=backend,
            source_transcript_ref=hook.get("transcript_path", ""),
        )
        # P5 seam (opt-in): capture task-lifecycle signal -> task.* events (§4.10, DR-37).
        # After the DURABLE flush, so task emission never jeopardizes the flush guarantee.
        if emit_task_events and result.get("entry_id"):
            emit_task_events_from_capture(
                data_root, capture_result, ts=now, source_episode=result["entry_id"]
            )
        return result

    # ------------------------------------------------------------------ #
    # Unknown event — return empty dict                                    #
    # ------------------------------------------------------------------ #
    return {}
