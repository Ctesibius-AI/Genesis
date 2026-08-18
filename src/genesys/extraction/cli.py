"""Fixtures-only drain CLI (spec §4.4/§4.5).

⚠ SAFETY: uses FakeGraph + a PASS FakeLLMBackend — it does NOT connect a real graph DB or the
Anthropic API and installs no live hook. The live drain (real engine/LLM) is a separate
owner-gated deploy step. `status` reports the queue; `run` drains once with fakes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from genesys.extraction.drain import drain_once
from genesys.graph.engine import FakeGraph
from genesys.ledger.entry import Extracted
from genesys.ledger.store import read_all
from genesys.workers.backend import FakeLLMBackend


def _cmd_status(args: argparse.Namespace) -> int:
    entries = read_all(Path(args.data))
    queued = sum(1 for e in entries if e.extracted is Extracted.NO)
    done = sum(1 for e in entries if e.extracted is Extracted.DONE)
    print(f"queued={queued} done={done} total={len(entries)}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    processed = drain_once(Path(args.data), FakeGraph(), FakeLLMBackend('{"verdict": "PASS", "flags": []}'),
                           ts=args.now)
    print(f"drained {len(processed)}: {processed}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesys-drain",
        description="P3.3 windowed drain over the ledger (FakeGraph/FakeLLM; no live engine or hook).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_s = sub.add_parser("status"); p_s.add_argument("--data", required=True); p_s.set_defaults(func=_cmd_status)
    p_r = sub.add_parser("run"); p_r.add_argument("--data", required=True)
    p_r.add_argument("--now", required=True); p_r.set_defaults(func=_cmd_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
