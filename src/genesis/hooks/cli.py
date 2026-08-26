"""CLI entry-point for Claude Code hooks — reads hook JSON from stdin, calls dispatch.

This is the ONLY module in genesis.hooks that may read the wall-clock. All other
modules (adapter.py, translate.py) are clock-injected so they remain testable
without monkeypatching datetime.

Usage (from Claude Code hook configuration):
    echo '<hook_json>' | GENESIS_DATA=/path/to/data genesis-hook

Environment variables:
    GENESIS_DATA        Path to the Genesis data root (default: "."). The old GENESIS_DATA_ROOT is
                        accepted for one release with a deprecation warning (D-FB-2), then removed.
    GENESIS_NOW         ISO-8601 timestamp override. If set, used as the clock.
                        If not set and the hook JSON carries a "now" key, that is used.
                        If neither is available, the wall-clock is read HERE only.

Spec: DR-08 (SessionStart), DR-14 (PreCompact), F-GENESIS-03 (provisional summary).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from genesis.hooks.adapter import dispatch


def _resolve_now(hook: dict) -> str:
    """Resolve the current ISO-8601 timestamp.

    Priority:
      1. GENESIS_NOW env var (allows test injection without touching stdin).
      2. hook JSON "now" key (the hook payload may carry it).
      3. Wall-clock — ONLY read here, isolated from adapter.py / translate.py.
    """
    from genesis.config import _getenv  # noqa: PLC0415 — GENESYS_* deprecation fallback (D-GCW-20)
    from_env = (_getenv("GENESIS_NOW") or "").strip()
    if from_env:
        return from_env
    from_hook = hook.get("now", "")
    if from_hook:
        return str(from_hook)
    # Wall-clock fallback — this is the ONE allowed place.
    return datetime.now(timezone.utc).isoformat()


# Bounded SessionStart drain (D-GCW-5 / D-GCW-18). Tunable; count + wall-clock bound.
SESSION_START_DRAIN_WINDOW = 5
SESSION_START_DRAIN_TIME_BUDGET_S = 20.0


def _session_start_drain(data_root: Path, now: str):
    """Return a zero-arg drain callable for dispatch's SessionStart branch (D-GCW-18 fix 1).

    Drains /save'd content queued in the ledger (D-GCW-18: /save is the sole materialization path).
    - GUARDED: skips the expensive live engine build entirely when nothing is queued (the common
      case, since automatic capture is WAL-only) — no cold-load on an idle start.
    - BOUNDED: count `window` + `time_budget_s` (defer the rest), per D-GCW-5.
    - EXCEPTION-SAFE: a missing graph extra / API error / LockHeld never breaks SessionStart; a
      queued item simply stays queued for the next start or `genesis-worker once` (AC-D2 posture).
    """
    def _drain() -> None:
        from genesis.ledger.entry import Extracted  # noqa: PLC0415
        from genesis.ledger.store import read_all  # noqa: PLC0415
        try:
            if not any(e.extracted is Extracted.NO for e in read_all(data_root)):
                return  # nothing queued → skip (no live engine build)
            from genesis.extraction.live import run_once  # noqa: PLC0415 — live-only
            run_once(data_root, now=now, window=SESSION_START_DRAIN_WINDOW,
                     time_budget_s=SESSION_START_DRAIN_TIME_BUDGET_S)
        except Exception:  # noqa: BLE001 — never break start; the queue survives for a later drain
            import logging  # noqa: PLC0415
            logging.getLogger("genesis.hooks").warning("SessionStart drain skipped (queue preserved)")
    return _drain


def main(argv: list[str] | None = None) -> int:
    """Read a JSON hook payload from stdin, dispatch it, print result as JSON to stdout.

    Returns exit code: 0 on success, 1 on error.
    """
    try:
        hook = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": f"invalid JSON on stdin: {exc}"}), file=sys.stdout)
        return 1

    from genesis.config import _data_root_env_value  # noqa: PLC0415 — canonical GENESIS_DATA (+ deprecated GENESIS_DATA_ROOT, D-FB-2)
    data_root = Path(_data_root_env_value() or ".")  # hook keeps its documented "." default (D-FB-1 removed "." for the MCP entry only)
    now = _resolve_now(hook)

    try:
        # SWITCH-ON (owner go-ahead 2026-08-19): live capture uses the WAL path.
        # wal=True → append+annotate (no per-save episode copy); cursor_delta=True →
        # bank only material after the session's last cursor (F4 guard). Default-OFF
        # legacy copy path remains available to callers that omit these.
        # annotate=False → automatic hooks are append-only (raw WAL safety net only);
        # no queue item is created. Only the manual /save path creates annotations.
        result = dispatch(hook, data_root, now=now, wal=True, cursor_delta=True,
                          annotate=False, drain=_session_start_drain(data_root, now))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}), file=sys.stdout)
        return 1

    # Structured hook output (JSON on stdout). SessionStart carries the user-visible confirmation
    # line in `systemMessage` (AC-CONF1) alongside the model-only additionalContext diary.
    print(json.dumps(result, ensure_ascii=False), file=sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
