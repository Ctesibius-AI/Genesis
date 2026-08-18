"""The structural read-time lock (spec §8.6 S2, §9.3 Fence 1).

`visible_perceived` is the only path by which a perceived edge about the principal reaches
Daimon's context — and only when the session ReleaseContext is open AND covers the anchor;
fail-closed otherwise. Task/recall/compile reads never return perceives about him (R-M).
"""

from __future__ import annotations

from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PRINCIPAL, PerceivesEdge
from genesys.persona.release import ReleaseContext, covers, is_open


def visible_perceived(dept: PerceptionDepartment, ctx: ReleaseContext | None, *,
                      subject: str = PRINCIPAL) -> list[PerceivesEdge]:
    if not is_open(ctx):
        return []  # fail-closed: None or closed context
    return [e for e in dept.edges_for_subject(subject) if covers(ctx, e.to)]


def for_task_read(dept: PerceptionDepartment, ctx: ReleaseContext | None = None, *,
                  subject: str = PRINCIPAL) -> list[PerceivesEdge]:
    # R-M: task/recall/compile use never consults her opinion of the principal.
    if subject == PRINCIPAL:
        return []
    return dept.edges_for_subject(subject)


def can_voice(ctx: ReleaseContext | None, anchor: str) -> bool:
    return covers(ctx, anchor)
