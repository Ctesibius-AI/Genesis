"""Fixtures-only CLI for the P2 diary (spec §4.7/§4.8).

⚠ SAFETY: installs no live SessionStart/PreCompact hook and reads no real transcript.
Uses the deterministic FakeBackend — the live Anthropic backend is wired only in a real
owner-gated run, not from this dev CLI. Live activation is a separate deploy step.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from genesys.config import DIARY_TOKEN_BUDGET, DIARY_WINDOW_DAYS
from genesys.diary.backend import FakeBackend
from genesys.diary.compiler import compile_diary
from genesys.diary.hooks import session_start_context


def _cmd_compile(args: argparse.Namespace) -> int:
    b = compile_diary(
        Path(args.data), now_iso=args.now, backend=FakeBackend(),
        window_days=DIARY_WINDOW_DAYS, cap_tokens=DIARY_TOKEN_BUDGET,
    )
    print(b.render())
    return 0


def _cmd_inject(args: argparse.Namespace) -> int:
    print(session_start_context(
        Path(args.data), now_iso=args.now, backend=FakeBackend(),
        window_days=DIARY_WINDOW_DAYS, cap_tokens=DIARY_TOKEN_BUDGET,
    ))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesys-diary",
        description="P2 diary compile/inject over the on-disk ledger (FakeBackend; no live hook).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("compile", _cmd_compile), ("inject", _cmd_inject)):
        p = sub.add_parser(name)
        p.add_argument("--data", required=True, help="data root (ledger + owned files)")
        p.add_argument("--now", required=True, help="ISO-8601 'now' for the window")
        p.set_defaults(func=fn)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
