"""F3 hook-wiring safety (spec §1 F3 row; §7 item 1).

Hook wiring is a silent SPOF: manual registration in .claude/settings.local.json; if
absent/reset, capture stops with no warning. This module gives (a) a wiring STATUS
read (which Genesys capture hooks are registered) and (b) a consent-based, idempotent,
MERGE-NEVER-CLOBBER writer. It does NOT auto-install: activation is an owner-gated
deploy step (pyproject deploy gate) -- write_hook_wiring refuses without consent=True
and is only ever invoked deliberately (the `genesys-save wire --yes` tool, Task 7).

The Stop -> response_validator.py hook is FOREIGN (not a Genesys capture hook) and must
survive every merge untouched. is_genesys_hook keys on the genesys.hooks.cli command so
we never touch it.
"""

from __future__ import annotations

import json
from pathlib import Path

GENESYS_EVENTS: tuple[str, ...] = ("SessionStart", "SessionEnd", "PreCompact")
_GENESYS_MARK = "genesys.hooks.cli"


def is_genesys_hook(command: str) -> bool:
    return _GENESYS_MARK in (command or "")


def _load(settings_path: Path) -> dict:
    try:
        obj = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _event_has_genesys(groups: list) -> bool:
    for grp in groups if isinstance(groups, list) else []:
        for h in (grp.get("hooks", []) if isinstance(grp, dict) else []):
            if isinstance(h, dict) and is_genesys_hook(h.get("command", "")):
                return True
    return False


def hook_wiring_status(settings_path: Path) -> dict[str, bool]:
    hooks = _load(settings_path).get("hooks", {})
    hooks = hooks if isinstance(hooks, dict) else {}
    return {e: _event_has_genesys(hooks.get(e, [])) for e in GENESYS_EVENTS}


def write_hook_wiring(settings_path: Path, *, command: str,
                      events: tuple[str, ...] = GENESYS_EVENTS,
                      consent: bool) -> dict[str, str]:
    if consent is not True:
        raise PermissionError(
            "write_hook_wiring is a deploy gate: pass consent=True explicitly "
            "(owner go-ahead). It never auto-installs a live hook.")
    settings = _load(settings_path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):  # never clobber a malformed shape silently
        raise ValueError("settings 'hooks' is not an object; refusing to clobber")
    actions: dict[str, str] = {}
    for event in events:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"settings hooks.{event} is not a list; refusing to clobber")
        if _event_has_genesys(groups):
            actions[event] = "already-wired"
            continue
        groups.append({"hooks": [{"type": "command", "command": command}]})
        actions[event] = "added"
    Path(settings_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings_path).write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return actions
