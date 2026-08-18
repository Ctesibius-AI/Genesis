"""Session-scoped ReleaseContext (spec §8.6, S2, App A.2).

A per-session object — never a graph write. The perceived-view is readable only while a
context is open and covers the anchor. `None` is treated as closed everywhere (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReleaseContext:
    open: bool = False
    open_anchors: list[str] = field(default_factory=list)
    scope: str = "topic"
    opened_by: str | None = None
    confirmed_at: str | None = None
    closed_by: str | None = None


def closed() -> ReleaseContext:
    return ReleaseContext(open=False)


def is_open(ctx: ReleaseContext | None) -> bool:
    return ctx is not None and ctx.open is True


def covers(ctx: ReleaseContext | None, anchor: str) -> bool:
    return is_open(ctx) and anchor in ctx.open_anchors
