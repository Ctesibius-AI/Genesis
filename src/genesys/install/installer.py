"""One-run installer (D-GCW-10) — idempotent, reversible, no-clobber, project-local ONLY.

Wires a workspace for Genesys: project-local capture hooks + a `.mcp.json` recall registration +
the `/save` command + the per-workspace store env. Guarantees:
- **Hooks are ALWAYS project-local** (AC-ISO2, red-line): written only to
  `<workspace>/.claude/settings.json`; never `~/.claude` or another project.
- **`CLAUDE.md` is never written** (AC-I1) — may print an optional snippet elsewhere.
- **Merge-never-clobber + idempotent** (AC-I2): re-running is a no-op; foreign hooks / mcp servers /
  env keys survive.
- **Fail-loud** (AC-I1): missing API key ⇒ refuse (no half-wired state).
- **Clean uninstall** (AC-I3): removes only Genesys-marked entries.

Store modes (D-GCW-4) choose only WHICH store the (always project-local) hooks target. Filesystem
logic is offline-testable; only launching Claude Code itself is live.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from genesys.hooks.wiring import GENESYS_EVENTS, unwire_hooks, write_hook_wiring

GENESYS_HOOK_COMMAND = "python3 -m genesys.hooks.cli"   # carries the genesys.hooks.cli mark
RECALL_MCP_SERVER = "genesys-recall"
_MCP_COMMAND = "python3"
_MCP_ARGS = ["-m", "genesys.recall.mcp_server"]
_ENV_KEYS = ("GENESYS_DATA", "GENESYS_DATA_ROOT", "GENESYS_DB_PATH", "GENESYS_GROUP_ID")

STORE_MODES = ("own-isolated", "shared-store-own-group", "shared-memory")


class InstallError(RuntimeError):
    """Fail-loud installer error (missing key, unknown mode) — never a half-wired state."""


def _ws_id(workspace: Path) -> str:
    return hashlib.sha1(str(Path(workspace).resolve()).encode()).hexdigest()[:12]


def compute_store(workspace: Path, data_root: Path, mode: str) -> tuple[str, str]:
    """(db_path, group_id) for a workspace under a store mode (D-GCW-4). Per-workspace isolation."""
    wsid = _ws_id(workspace)
    stores = Path(data_root) / "stores"
    if mode == "own-isolated":       # physical + logical wall (default, strongest)
        return str(stores / wsid / "graph.db"), f"ws-{wsid}"
    if mode == "shared-store-own-group":  # one backend, logical wall only
        return str(stores / "shared" / "graph.db"), f"ws-{wsid}"
    if mode == "shared-memory":      # pooled — one memory across dirs
        return str(stores / "shared" / "graph.db"), "shared"
    raise InstallError(f"unknown store mode {mode!r}; expected one of {STORE_MODES}")


def genesys_env(data_root: Path, db_path: str, group_id: str) -> dict:
    # GENESYS_DATA (config) and GENESYS_DATA_ROOT (hooks/cli) are two names for the same root
    # today — set BOTH (duplication flagged for follow-up cleanup, not reconciled here).
    return {"GENESYS_DATA": str(data_root), "GENESYS_DATA_ROOT": str(data_root),
            "GENESYS_DB_PATH": db_path, "GENESYS_GROUP_ID": group_id}


def _load_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _merge_env(settings_path: Path, env: dict) -> None:
    settings = _load_json(settings_path)
    block = settings.get("env")
    block = block if isinstance(block, dict) else {}
    block.update(env)  # our keys win; foreign env keys untouched
    settings["env"] = block
    _write_json(settings_path, settings)


def _merge_mcp(mcp_path: Path, env: dict) -> None:
    cfg = _load_json(mcp_path)
    servers = cfg.get("mcpServers")
    servers = servers if isinstance(servers, dict) else {}
    servers[RECALL_MCP_SERVER] = {"command": _MCP_COMMAND, "args": list(_MCP_ARGS), "env": dict(env)}
    cfg["mcpServers"] = servers  # foreign servers preserved
    _write_json(mcp_path, cfg)


def install(workspace: Path, *, data_root: Path, api_key_present: bool,
            mode: str = "own-isolated", profile: str = "stdio-lite",
            save_command_src: Path | None = None) -> dict:
    workspace, data_root = Path(workspace), Path(data_root)
    if mode not in STORE_MODES:
        raise InstallError(f"unknown store mode {mode!r}; expected one of {STORE_MODES}")
    if not api_key_present:
        raise InstallError("ANTHROPIC_API_KEY is not set — refusing a half-wired install (AC-I1).")

    claude = workspace / ".claude"
    settings = claude / "settings.json"
    db_path, group_id = compute_store(workspace, data_root, mode)
    env = genesys_env(data_root, db_path, group_id)

    # 1) capture hooks — PROJECT-LOCAL ONLY (AC-ISO2), merge-never-clobber, consent-gated.
    hook_actions = write_hook_wiring(settings, command=GENESYS_HOOK_COMMAND, consent=True)
    # 2) per-workspace store env (into the project-local settings).
    _merge_env(settings, env)
    # 3) recall MCP registration.
    _merge_mcp(workspace / ".mcp.json", env)
    # 4) /save command into the project commands dir.
    if save_command_src is not None and Path(save_command_src).exists():
        dest = claude / "commands" / "save.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(Path(save_command_src).read_text(encoding="utf-8"), encoding="utf-8")
    # 5) provision the store directory (never a /tmp graph — D-GCW-2).
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # NOTE: CLAUDE.md is intentionally never read or written (AC-I1).

    return {"workspace": str(workspace), "profile": profile, "mode": mode,
            "db_path": db_path, "group_id": group_id, "hooks": hook_actions,
            "settings": str(settings)}


def uninstall(workspace: Path) -> dict:
    """Remove only Genesys-marked wiring (AC-I3); foreign hooks / servers / env keys survive."""
    workspace = Path(workspace)
    claude = workspace / ".claude"
    settings = claude / "settings.json"
    actions: dict = {}
    if settings.exists():
        actions["hooks"] = unwire_hooks(settings)
        s = _load_json(settings)
        block = s.get("env")
        if isinstance(block, dict):
            for k in _ENV_KEYS:
                block.pop(k, None)
            if block:
                s["env"] = block
            else:
                s.pop("env", None)
            _write_json(settings, s)
    mcp = workspace / ".mcp.json"
    if mcp.exists():
        cfg = _load_json(mcp)
        servers = cfg.get("mcpServers")
        if isinstance(servers, dict) and RECALL_MCP_SERVER in servers:
            servers.pop(RECALL_MCP_SERVER, None)
            if servers:
                cfg["mcpServers"] = servers
            else:
                cfg.pop("mcpServers", None)
            _write_json(mcp, cfg)
    save_cmd = claude / "commands" / "save.md"
    if save_cmd.exists():
        save_cmd.unlink()
        actions["save_command"] = "removed"
    return actions
