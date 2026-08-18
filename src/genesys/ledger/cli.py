"""Fixtures-only CLI for P1 save + doctor (spec §4.3, §4.14).

⚠ SAFETY: does NOT install/activate a live Claude Code hook and does NOT read a real
transcript. ``save`` operates on a provided JSON fixture describing one episode; ``doctor``
operates on an on-disk data root. Live activation is a separate owner-gated deploy step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from genesys.doctor import doctor_requeue
from genesys.save import fast_path_save

_SAVE_FIELDS = (
    "raw_span", "summary", "session_id", "speakers",
    "span_start", "span_end", "ts",
)
_SAVE_OPTIONAL = ("source_transcript_ref", "salience", "prev", "continues")


def _cmd_save(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    missing = [f for f in _SAVE_FIELDS if f not in payload]
    if missing:
        print(f"fixture missing required fields: {missing}", file=sys.stderr)
        return 2
    kw = {f: payload[f] for f in _SAVE_FIELDS}
    kw.update({f: payload[f] for f in _SAVE_OPTIONAL if f in payload})
    entry = fast_path_save(Path(args.data), **kw)
    print(f"saved {entry.entry_id} (extracted={entry.extracted.value}) -> {args.data}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    requeued = doctor_requeue(Path(args.data))
    print(f"doctor re-queued {len(requeued)} wedged entr(y/ies): {requeued}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesys-save",
        description="P1 fast-path save + doctor over FIXTURES only (no live hook).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="persist one episode from a JSON fixture")
    p_save.add_argument("fixture", help="JSON fixture describing one episode")
    p_save.add_argument("--data", required=True, help="data root (owned files + ledger)")
    p_save.set_defaults(func=_cmd_save)

    p_doc = sub.add_parser("doctor", help="re-queue wedged in-progress entries")
    p_doc.add_argument("--data", required=True, help="data root")
    p_doc.set_defaults(func=_cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
