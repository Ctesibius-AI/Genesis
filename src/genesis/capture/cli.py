"""CLI entrypoint for the DR-37 capture-mirror logic (spec v1.5 §4.2a).

⚠ SAFETY: this CLI does NOT install or activate any live Claude Code hook and does NOT
read any real transcript. It operates ONLY on a provided fixture file of already-parsed
transcript events (JSON: either a list of event objects, or an object with an
``"events"`` key). Activation against a live session is a separate deploy step that
requires the owner's explicit go-ahead (spec §14 Step 0).

Usage:
    genesis-capture <events.json> [--out DIR]

Given fixture events, it produces the two owned projections (flight recorder +
memory-grade), with the DR-38 scrubber already applied to all content. With ``--out`` it
writes ``flight_recorder.json`` and ``memory_grade.json`` into DIR; without it, prints a
short summary to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import List

from genesis.capture.mirror import CaptureResult, TranscriptEvent, mirror_events


def _load_events(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "events" in data:
        data = data["events"]
    if not isinstance(data, list):
        raise ValueError("fixture must be a JSON list of events or {'events': [...]}")
    return data


def _projection_to_dict(result: CaptureResult) -> dict:
    return {
        "flight_recorder": [asdict(e) for e in result.flight_recorder.entries],
        "memory_grade": [asdict(e) for e in result.memory_grade.entries],
        "scrub_matches": [asdict(m) for m in result.scrub_matches],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genesis-capture",
        description=(
            "DR-37 capture-mirror over FIXTURE events only. Does not install a live "
            "hook or read a real transcript (activation is a separate deploy step)."
        ),
    )
    parser.add_argument("events", type=Path, help="JSON fixture of transcript events")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="directory to write flight_recorder.json + memory_grade.json into",
    )
    args = parser.parse_args(argv)

    events = _load_events(args.events)
    result = mirror_events(events)

    if args.out:
        out = args.out
        out.mkdir(parents=True, exist_ok=True)
        payload = _projection_to_dict(result)
        (out / "flight_recorder.json").write_text(
            json.dumps(payload["flight_recorder"], indent=2), encoding="utf-8"
        )
        (out / "memory_grade.json").write_text(
            json.dumps(payload["memory_grade"], indent=2), encoding="utf-8"
        )
        (out / "scrub_matches.json").write_text(
            json.dumps(payload["scrub_matches"], indent=2), encoding="utf-8"
        )
        print(
            f"wrote flight_recorder ({len(result.flight_recorder.entries)} entries), "
            f"memory_grade ({len(result.memory_grade.entries)} entries), "
            f"{len(result.scrub_matches)} redactions -> {out}"
        )
    else:
        print(
            f"flight_recorder: {len(result.flight_recorder.entries)} entries\n"
            f"memory_grade:    {len(result.memory_grade.entries)} entries\n"
            f"redactions:      {len(result.scrub_matches)}"
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
