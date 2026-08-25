"""Manual save ritual (CS4) — capture the current session window as a SALIENT annotation.

`find_current_transcript`: locates the newest .jsonl under ~/.claude/projects/<encoded>/ for a
given project_cwd. `save_moment`: flushes any un-captured transcript tail (Part A incremental
path), then annotates the already-captured WAL window as SALIENT via ``save_annotation`` —
WITHOUT re-appending the whole transcript (Part B: save references, does not re-capture).

Owner's model:
  - Automatic hooks capture each reply ONCE (incremental WAL append, no annotations).
  - A manual save REFERENCES the already-captured window by creating a SALIENT annotation
    (last_save_cursor → now) over the WAL, after optionally flushing any uncaptured tail.

No new dependencies; stdlib + internal genesis modules only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from genesis.capture.mirror import mirror_events
from genesis.config import get_assistant_name, get_principal
from genesis.hooks.adapter import _read_jsonl
from genesis.hooks.translate import cc_transcript_to_events
from genesis.ledger.entry import LedgerEntry
from genesis.save_cursor import latest_span_end_for_session
from genesis.wal.annotate import save_annotation
from genesis.wal.courier import append_and_annotate
from genesis.wal.record import WalRecord
from genesis.wal.write_cursor import read_captured_count, write_captured_count


def _encoded_project_dir(project_cwd: Path, projects_root: Path) -> Path:
    """The Claude Code transcript dir for a project: ~/.claude/projects/<cwd with '/'→'-'>."""
    encoded = str(Path(project_cwd).expanduser().resolve()).replace("/", "-")
    return projects_root / encoded


def find_current_transcript(
    project_cwd: Path,
    *,
    projects_root: Path | None = None,
) -> Path | None:
    """Return the newest .jsonl **within THIS project's** transcript dir, or None (F-06.3).

    Claude Code stores transcripts at ~/.claude/projects/<encoded>/*.jsonl where
    <encoded> = the project cwd with '/' replaced by '-'. Selection is scoped to that ONE
    directory — NEVER a global newest-mtime across all projects, which could ingest a
    concurrent OTHER project's transcript into this workspace's memory (cross-project
    contamination at the capture door, undercutting the group_id/db_path isolation enforced
    downstream). Returns None when this project has no transcript — the caller fails loud
    rather than borrowing a neighbour's.

    Args:
        project_cwd: the invoking project's working directory (used to select its dir).
        projects_root: override for ~/.claude/projects (injectable for tests).
    """
    if projects_root is None:
        projects_root = Path.home() / ".claude" / "projects"
    project_dir = _encoded_project_dir(project_cwd, projects_root)
    if not project_dir.is_dir():
        return None
    candidates = list(project_dir.glob("*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_transcript_by_session_id(
    session_id: str,
    *,
    projects_root: Path | None = None,
) -> Path | None:
    """Return the EXACT transcript for a session id: ~/.claude/projects/*/<session_id>.jsonl.

    Claude Code names each session's transcript ``<session_id>.jsonl`` and exports
    ``CLAUDE_CODE_SESSION_ID`` to shell commands. Matching on it identifies the session that
    invoked ``/save`` unambiguously — no mtime race across concurrent terminals, no dependence
    on cwd/project encoding. Preferred over ``find_current_transcript`` whenever the id is known.

    Args:
        session_id: the invoking session's id (from ``$CLAUDE_CODE_SESSION_ID``).
        projects_root: override for ~/.claude/projects (injectable for tests).

    Returns:
        The matching transcript Path, or None if the id is empty / no match exists.
    """
    if not session_id:
        return None
    if projects_root is None:
        projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.is_dir():
        return None
    matches = list(projects_root.rglob(f"{session_id}.jsonl"))
    return matches[0] if matches else None


def save_moment(
    data_root: Path,
    *,
    transcript_path: Path,
    session_id: str,
    now: str,
    note: str,
    speakers: tuple[str, ...] | list[str] | None = None,
) -> LedgerEntry | None:
    """Capture the current session window as a SALIENT annotation with `note` as its jot.

    Part B fix — save REFERENCES, does not re-capture:
      1. Flush only the *tail* (any new records since the last WAL append for this session,
         via the Part-A incremental write-cursor path) so the current in-progress reply is
         captured ONCE.
      2. Create the SALIENT annotation over the already-captured WAL window using
         ``save_annotation`` directly — NOT ``append_and_annotate`` — so the window content
         is NOT re-appended again.

    Args:
        data_root: Genesis data root (ledger + WAL live here).
        transcript_path: Path to the Claude Code session .jsonl transcript.
        session_id: The CC session identifier (used for cursor delta + structural linking).
        now: ISO-8601 timestamp for this save moment (clock-injected by caller).
        note: The owner's label / reason — stored as the jot and used as the entry summary.
        speakers: Speaker names for the WAL record (default: the configured
            [principal, assistant] — see genesis.config).

    Returns:
        The created LedgerEntry (a SALIENT annotation), or None if there is nothing in the
        WAL window (empty transcript, no memory-grade material captured at all).
    """
    if speakers is None:
        speakers = (get_principal(), get_assistant_name())
    all_records = _read_jsonl(transcript_path)

    # Step 1: flush the uncaptured tail (if any).
    # If len(all_records) < already_captured the transcript was compacted/rewritten shorter;
    # re-derive from record 0 so post-compaction content is not silently lost.
    already_captured = read_captured_count(data_root, session_id)
    if len(all_records) < already_captured:
        new_records = all_records
    else:
        new_records = all_records[already_captured:]
    if new_records:
        new_events = cc_transcript_to_events(new_records)
        new_capture = mirror_events(new_events)
        tail_cursor = latest_span_end_for_session(data_root, session_id)
        # Append-only flush: append WAL, no annotation yet.
        append_and_annotate(
            data_root,
            capture_result=new_capture,
            cursor=tail_cursor,
            now=now,
            session_id=session_id,
            speakers=list(speakers),
            jot="",
            annotate=False,
        )
        write_captured_count(data_root, session_id, len(all_records))

    # Step 2: check that there is something in the WAL for this session.
    # If no records at all were ever captured (empty transcript, nothing to save), return None.
    if not all_records:
        return None

    # Step 3: annotate the window (last_save_cursor → now) as SALIENT — reference only,
    # no re-capture. The window is fully constituted by the WAL appends above + prior rings.
    window_cursor = latest_span_end_for_session(data_root, session_id)
    # After the tail flush, the write cursor advanced to len(all_records) but the ledger
    # cursor (from annotations) hasn't moved yet — that's correct: it's the window start.
    return save_annotation(
        data_root,
        start_ts=window_cursor,
        end_ts=now,
        jot=note,
        session_id=session_id,
        speakers=list(speakers),
        record=WalRecord.MEMORY_GRADE,
    )


def main() -> None:
    """CLI entry point for genesis-save-moment."""
    parser = argparse.ArgumentParser(
        prog="genesis-save-moment",
        description="Capture the current session window as a labelled annotation (/save).",
    )
    parser.add_argument("--note", default="",
                        help="Reason / label for this save (used as the entry's jot)")
    parser.add_argument("--data-root", default="~/.genesis/data",
                        help="Genesis data root (default: ~/.genesis/data)")
    parser.add_argument("--project-cwd",
                        default=str(Path.cwd()),
                        help="Project working directory for transcript auto-detection")
    parser.add_argument("--session-id", default="",
                        help="Session ID override (default: transcript filename stem)")
    parser.add_argument("--now", default="",
                        help="ISO-8601 timestamp override (default: wall-clock UTC)")
    parser.add_argument("--transcript", default="",
                        help="Path to transcript .jsonl override (default: auto-detected)")
    parser.add_argument("--extract", action=argparse.BooleanOptionalAction, default=True,
                        help="Immediately run the extraction team on the save so the facts land "
                             "in the graph now (default: on). Use --no-extract to only queue it.")
    args = parser.parse_args()

    data_root = Path(args.data_root).expanduser()
    project_cwd = Path(args.project_cwd).expanduser()
    now = args.now or datetime.now(timezone.utc).isoformat()

    # F-06.3 layer 2: resolve the session id from the flag OR CLAUDE_CODE_SESSION_ID (CC exports it
    # to shell commands) BEFORE any mtime path — old wiring without --session-id gets the safe route.
    session_id = args.session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "")

    if args.transcript:
        transcript_path: Path | None = Path(args.transcript).expanduser()
    elif session_id:
        # EXACT: the invoking session's own transcript by id — no cross-terminal mtime race. If it
        # has no transcript on disk, REFUSE (never fall to a global newest that could be a neighbour's).
        transcript_path = find_transcript_by_session_id(session_id)
        if transcript_path is None:
            print(f"save_moment: no transcript for session {session_id!r}; refusing to guess "
                  "another session's. Pass --transcript to override.")
            return
    else:
        # No session id → newest WITHIN this project's dir only (F-06.3), never global.
        transcript_path = find_current_transcript(project_cwd)
        if transcript_path is None:
            print("save_moment: cannot identify this session's transcript (no CLAUDE_CODE_SESSION_ID "
                  "and no transcript in this project's dir). Pass --session-id.")
            return

    session_id = session_id or transcript_path.stem

    entry = save_moment(
        data_root,
        transcript_path=transcript_path,
        session_id=session_id,
        now=now,
        note=args.note,
    )
    if entry is None:
        print("save_moment: nothing new to save.")
        return
    print(f"save_moment: {entry.entry_id} saved")

    if args.extract:
        # Owner model: save -> queue -> the extraction team runs IMMEDIATELY, so the facts +
        # verbatim land in memory now (not on a later manual drain). Lazy import keeps the
        # module offline-importable (the live path pulls anthropic + falkordb). Fail-safe: the
        # save is already queued, so an extraction hiccup never loses it.
        try:
            from genesis.extraction.live import run_once  # noqa: PLC0415 — lazy, live-only
            processed = run_once(data_root, now=now)
            if processed:
                print(f"save_moment: extracted {len(processed)} item(s) into memory: {processed}")
            else:
                print("save_moment: extraction ran — nothing new resolved.")
        except Exception as exc:  # noqa: BLE001 — never lose the save on an extraction error
            print(f"save_moment: SAVED and queued, but extraction failed ({exc}); "
                  f"run `genesis-worker once` to retry.")


if __name__ == "__main__":  # `python -m genesis.save_moment` (the /save command's entry)
    main()
