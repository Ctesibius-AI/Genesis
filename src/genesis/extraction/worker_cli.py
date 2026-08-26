"""Live drain worker CLI — real graph/LLM/embedder (spec §4.14, DR-05c, §8).

Entry point: genesis-worker (see pyproject.toml [project.scripts]).
Subcommands:
  once  — run_once then exit, printing processed entry IDs.
  serve — run_forever (blocking loop; intended for launchd KeepAlive).

SAFETY: This CLI connects the real Anthropic API and the real FalkorDB graph. Do NOT call
it during the offline test suite. The offline suite uses genesis-drain (fixtures-only).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DEFAULT_DATA_ROOT = Path.home() / ".genesis" / "data"


def _cmd_once(args: argparse.Namespace) -> int:
    """Run a single live drain pass and print processed entry IDs."""
    from datetime import datetime, timezone  # noqa: PLC0415 — stdlib

    from genesis.extraction.live import run_once  # noqa: PLC0415
    from genesis.graph.client import PersistenceError  # noqa: PLC0415

    data_root = Path(args.data_root)
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        processed = run_once(data_root, now=now)
    except PersistenceError as exc:
        # FAIL LOUD (harness-savefail): the store did NOT persist this pass. "processed N" is never
        # the last word — this pass's entries were reverted to queued and will re-extract next run.
        print(f"PERSISTENCE FAILURE: the store did not persist this pass ({exc}); its entries were "
              f"reverted to queued — re-run the worker to re-extract. Nothing was durably saved.",
              file=sys.stderr)
        return 2
    print(f"processed {len(processed)}: {processed}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    """Run the drain loop indefinitely (for launchd KeepAlive use)."""
    from genesis.extraction.live import run_forever  # noqa: PLC0415

    data_root = Path(args.data_root)
    interval = float(args.interval)
    print(f"[genesis-worker] starting serve loop (data_root={data_root}, interval={interval}s)",
          flush=True)
    run_forever(data_root, interval_s=interval)
    return 0  # unreachable under normal operation


def main(argv: list[str] | None = None) -> int:
    """Entry point for genesis-worker CLI (spec §4.14)."""
    parser = argparse.ArgumentParser(
        prog="genesis-worker",
        description="Live drain worker — real graph/LLM/embedder. Not safe in the offline suite.",
    )
    parser.add_argument(
        "--data-root",
        dest="data_root",
        default=str(_DEFAULT_DATA_ROOT),
        help="Path to the Genesis data directory (default: ~/.genesis/data).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_once = sub.add_parser("once", help="Run one drain pass and exit.")
    p_once.set_defaults(func=_cmd_once)

    p_serve = sub.add_parser("serve", help="Run drain loop indefinitely (launchd mode).")
    p_serve.add_argument(
        "--interval",
        default="10",
        help="Seconds between drain passes (default: 10).",
    )
    p_serve.set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
