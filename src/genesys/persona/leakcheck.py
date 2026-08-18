"""V-1a leak check (spec §8.6 barrier, validation V-1a).

A leak-*check*, not the mechanism (the lock is the mechanism). Confirms no perceived anchor is
served without an open context covering it, and that a served opinion has a preceding
key+confirm in the journal audit trail.
"""

from __future__ import annotations

from pathlib import Path

from genesys.journal.journal import read_journal
from genesys.persona.release import ReleaseContext, covers


def unkeyed_leak(served_anchors: list[str], ctx: ReleaseContext | None) -> list[str]:
    return [a for a in served_anchors if not covers(ctx, a)]


def assert_no_unkeyed_leak(served_anchors: list[str], ctx: ReleaseContext | None) -> None:
    leaked = unkeyed_leak(served_anchors, ctx)
    if leaked:
        raise AssertionError(f"V-1a leak: served without an open key: {leaked}")


def release_journaled_before(data_root: Path, *, ts: str) -> bool:
    for e in read_journal(data_root):
        if e.action in ("opinion-confirm", "opinion-release") and e.ts <= ts:
            return True
    return False
