"""CLI entry-point for Claude Code hooks — reads hook JSON from stdin, calls dispatch.

This is the ONLY module in genesys.hooks that may read the wall-clock. All other
modules (adapter.py, translate.py) are clock-injected so they remain testable
without monkeypatching datetime.

Usage (from Claude Code hook configuration):
    echo '<hook_json>' | GENESYS_DATA_ROOT=/path/to/data genesys-hook

Environment variables:
    GENESYS_DATA_ROOT   Path to the Genesys data root (default: ".").
    GENESYS_NOW         ISO-8601 timestamp override. If set, used as the clock.
                        If not set and the hook JSON carries a "now" key, that is used.
                        If neither is available, the wall-clock is read HERE only.

Spec: DR-08 (SessionStart), DR-14 (PreCompact), F-GENESYS-03 (provisional summary).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from genesys.hooks.adapter import dispatch


def _resolve_now(hook: dict) -> str:
    """Resolve the current ISO-8601 timestamp.

    Priority:
      1. GENESYS_NOW env var (allows test injection without touching stdin).
      2. hook JSON "now" key (the hook payload may carry it).
      3. Wall-clock — ONLY read here, isolated from adapter.py / translate.py.
    """
    from_env = os.environ.get("GENESYS_NOW", "").strip()
    if from_env:
        return from_env
    from_hook = hook.get("now", "")
    if from_hook:
        return str(from_hook)
    # Wall-clock fallback — this is the ONE allowed place.
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    """Read a JSON hook payload from stdin, dispatch it, print result as JSON to stdout.

    Returns exit code: 0 on success, 1 on error.
    """
    try:
        hook = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": f"invalid JSON on stdin: {exc}"}), file=sys.stdout)
        return 1

    data_root = Path(os.environ.get("GENESYS_DATA_ROOT", "."))
    now = _resolve_now(hook)

    try:
        # SWITCH-ON (owner go-ahead 2026-08-19): live capture uses the WAL path.
        # wal=True → append+annotate (no per-save episode copy); cursor_delta=True →
        # bank only material after the session's last cursor (F4 guard). Default-OFF
        # legacy copy path remains available to callers that omit these.
        # annotate=False → automatic hooks are append-only (raw WAL safety net only);
        # no queue item is created. Only the manual /save path creates annotations.
        result = dispatch(hook, data_root, now=now, wal=True, cursor_delta=True,
                          annotate=False)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}), file=sys.stdout)
        return 1

    # Structured hook output (JSON on stdout). SessionStart carries the user-visible confirmation
    # line in `systemMessage` (AC-CONF1) alongside the model-only additionalContext diary.
    print(json.dumps(result, ensure_ascii=False), file=sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
