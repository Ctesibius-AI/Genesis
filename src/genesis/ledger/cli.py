"""Fixtures-only CLI for P1 save + doctor (spec §4.3, §4.14).

⚠ SAFETY: does NOT install/activate a live Claude Code hook and does NOT read a real
transcript. ``save`` operates on a provided JSON fixture describing one episode; ``doctor``
operates on an on-disk data root. Live activation is a separate owner-gated deploy step.

The ``wire`` subcommand is a consent-gated deploy tool — it prints wiring status by default
and only writes when ``--yes`` is passed explicitly (owner go-ahead required).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from genesis.doctor import doctor_deadman, doctor_requeue
from genesis.hooks.wiring import hook_wiring_status, write_hook_wiring
from genesis.save import fast_path_save

_SAVE_FIELDS = (
    "raw_span", "summary", "session_id", "speakers",
    "span_start", "span_end", "ts",
)
_SAVE_OPTIONAL = ("source_transcript_ref", "prev", "continues")


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
    if getattr(args, "deadman", False):
        now = args.now or datetime.now(timezone.utc).isoformat()  # CLI clock boundary
        settings = Path(args.settings) if getattr(args, "settings", None) else None
        r = doctor_deadman(Path(args.data), now=now,
                           threshold_hours=args.threshold_hours, settings_path=settings)
        status = "STALE" if r.stale else "OK"
        age = "no capture ring on record" if r.age_hours is None else f"{r.age_hours:.1f}h ago"
        print(f"deadman [{status}] last ring: {r.last_ring_ts or '(none)'} ({age})")
        if r.wired is not None:
            for event, ok in r.wired.items():
                print(f"  hook {event}: {'wired' if ok else 'UNWIRED'}")
        return 0
    requeued = doctor_requeue(Path(args.data))
    print(f"doctor re-queued {len(requeued)} wedged entr(y/ies): {requeued}")
    return 0


def _cmd_wire(args: argparse.Namespace) -> int:
    settings = Path(args.settings)
    if not args.yes:
        status = hook_wiring_status(settings)
        print(f"wiring status: {status}")
        print("deploy gate: will NOT write without --yes (owner go-ahead required).")
        return 0
    actions = write_hook_wiring(settings, command=args.command, consent=True)
    print(f"wired (merge-never-clobber): {actions}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesis-save",
        description="P1 fast-path save + doctor over FIXTURES only (no live hook).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="persist one episode from a JSON fixture")
    p_save.add_argument("fixture", help="JSON fixture describing one episode")
    p_save.add_argument("--data", required=True, help="data root (owned files + ledger)")
    p_save.set_defaults(func=_cmd_save)

    p_doc = sub.add_parser("doctor", help="re-queue wedged in-progress entries; or --deadman report")
    p_doc.add_argument("--data", required=True, help="data root")
    p_doc.add_argument("--deadman", action="store_true",
                       help="print the F3 last-ring deadman + wiring report")
    p_doc.add_argument("--settings", help="path to .claude/settings.local.json (wiring check)")
    p_doc.add_argument("--now", help="ISO-8601 now override (default: wall-clock)")
    p_doc.add_argument("--threshold-hours", type=float, default=24.0,
                       help="stale threshold in hours (default 24)")
    p_doc.set_defaults(func=_cmd_doctor)

    p_wire = sub.add_parser("wire", help="consent-gated hook wiring (merge-never-clobber)")
    p_wire.add_argument("--settings", required=True,
                        help="path to the settings file to merge into")
    p_wire.add_argument("--command", required=True,
                        help="the genesis.hooks.cli hook command to register")
    p_wire.add_argument("--yes", action="store_true",
                        help="owner consent — actually write (deploy gate)")
    p_wire.set_defaults(func=_cmd_wire)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
