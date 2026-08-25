"""F3 hook-wiring safety (spec §1 F3 row; §7 item 1).

Hook wiring is a silent SPOF: manual registration in .claude/settings.local.json; if
absent/reset, capture stops with no warning. This module gives (a) a wiring STATUS
read (which Genesis capture hooks are registered) and (b) a consent-based, idempotent,
MERGE-NEVER-CLOBBER writer. It does NOT auto-install: activation is an owner-gated
deploy step (pyproject deploy gate) -- write_hook_wiring refuses without consent=True
and is only ever invoked deliberately (the `genesis-save wire --yes` tool, Task 7).

The Stop -> response_validator.py hook is FOREIGN (not a Genesis capture hook) and must
survive every merge untouched. is_genesis_hook keys on the genesis.hooks.cli command so
we never touch it.
"""

from __future__ import annotations

import json
from pathlib import Path

# Stop added per D-GCW-18 (crash durability): capture the delta after each turn so an abnormal
# termination before SessionEnd/PreCompact doesn't lose the session (design §5a "Stop/SessionEnd").
GENESIS_EVENTS: tuple[str, ...] = ("SessionStart", "Stop", "SessionEnd", "PreCompact")
_GENESIS_MARK = "genesis.hooks.cli"
# Rename migration (D-GCW-20): recognize the OLD mark too, for ONE release, so pre-rename
# installs' hooks stay status/uninstall-recognized (no orphaned `genesys` hooks). New installs
# wire the genesis mark; uninstall then cleans either.
_LEGACY_MARK = "genesys.hooks.cli"


def is_genesis_hook(command: str) -> bool:
    cmd = command or ""
    return _GENESIS_MARK in cmd or _LEGACY_MARK in cmd


def _load(settings_path: Path) -> dict:
    try:
        obj = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _event_has_genesis(groups: list) -> bool:
    for grp in groups if isinstance(groups, list) else []:
        for h in (grp.get("hooks", []) if isinstance(grp, dict) else []):
            if isinstance(h, dict) and is_genesis_hook(h.get("command", "")):
                return True
    return False


def hook_wiring_status(settings_path: Path) -> dict[str, bool]:
    hooks = _load(settings_path).get("hooks", {})
    hooks = hooks if isinstance(hooks, dict) else {}
    return {e: _event_has_genesis(hooks.get(e, [])) for e in GENESIS_EVENTS}


def write_hook_wiring(settings_path: Path, *, command: str,
                      events: tuple[str, ...] = GENESIS_EVENTS,
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
        if _event_has_genesis(groups):
            actions[event] = "already-wired"
            continue
        groups.append({"hooks": [{"type": "command", "command": command}]})
        actions[event] = "added"
    Path(settings_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings_path).write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return actions


def _group_has_genesis(grp) -> bool:
    return isinstance(grp, dict) and any(
        isinstance(h, dict) and is_genesis_hook(h.get("command", "")) for h in grp.get("hooks", []))


def unwire_hooks(settings_path: Path, *, events: tuple[str, ...] = GENESIS_EVENTS) -> dict[str, str]:
    """Remove ONLY Genesis hook groups (AC-I3 uninstall); foreign hooks survive untouched.

    A Genesis group is one whose command carries the `genesis.hooks.cli` mark. Non-Genesis groups
    (e.g. a foreign Stop → response_validator hook) are preserved. Empty event keys are dropped.
    """
    settings = _load(settings_path)
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return {}
    actions: dict[str, str] = {}
    for event in events:
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            continue
        kept = [g for g in groups if not _group_has_genesis(g)]
        actions[event] = "removed" if len(kept) < len(groups) else "absent"
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    Path(settings_path).write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return actions
