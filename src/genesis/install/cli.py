"""`genesis-install` — the one-run installer CLI (D-GCW-10).

Wires the current (or a given) workspace: platform-conditional profile → project-local hooks +
`.mcp.json` + `/save` + per-workspace store env. `--uninstall` cleanly reverses it. Fail-loud on a
missing API key or an unmet platform floor with no Docker fallback (AC-I1 / AC-PLAT1).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from genesis.install.installer import STORE_MODES, InstallError, install, uninstall
from genesis.install.platform import PlatformError, detect_platform, select_profile


def _default_save_command() -> Path:
    # the /save command shipped in the repo (commands/save.md at the package root's parent)
    return Path(__file__).resolve().parents[3] / "commands" / "save.md"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="genesis-install", description="Wire Genesis into a workspace.")
    p.add_argument("--workspace", default=str(Path.cwd()), help="Workspace to wire (default: cwd).")
    p.add_argument("--data-root", default=str(Path.home() / ".genesis" / "data"),
                   help="Genesis data root for stores + the ledger.")
    p.add_argument("--mode", default="own-isolated", choices=STORE_MODES,
                   help="Which store the (always project-local) hooks target (D-GCW-4).")
    p.add_argument("--uninstall", action="store_true", help="Remove only Genesis-marked wiring.")
    args = p.parse_args(argv)

    workspace = Path(args.workspace).expanduser()

    if args.uninstall:
        actions = uninstall(workspace)
        sys.stdout.write(f"Genesis uninstalled from {workspace}: {actions}\n")
        return 0

    try:  # pragma: no cover - platform detection reads the real host
        profile = select_profile(detect_platform(), docker_available=_docker_available())
    except PlatformError as exc:
        sys.stderr.write(f"install refused: {exc}\n")
        return 2

    try:
        report = install(
            workspace, data_root=Path(args.data_root).expanduser(),
            api_key_present=bool(os.environ.get("ANTHROPIC_API_KEY")),
            mode=args.mode, profile=profile, save_command_src=_default_save_command(),
        )
    except InstallError as exc:
        sys.stderr.write(f"install refused: {exc}\n")
        return 2
    sys.stdout.write(
        f"Genesis wired into {workspace} (profile={report['profile']}, mode={report['mode']}).\n"
        f"Store: {report['db_path']} (group {report['group_id']}). CLAUDE.md untouched.\n"
        "Note: the session-start memory line shows in the Claude Code CLI; the VS Code extension\n"
        "      currently hides it (upstream CC bug #15344, waiver W-GCW-1).\n"
    )
    return 0


def _docker_available() -> bool:  # pragma: no cover - shells out on the real host
    import shutil
    return shutil.which("docker") is not None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
