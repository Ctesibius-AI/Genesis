"""The answering register — D-SOUL-1 (spec §12, §8.6).

The one place the §8.6 lock gates an actual voicing of Daimon's opinion. Voiced ONLY when the
ReleaseContext covers the anchor (P6.2 can_voice); as her opinion, in her words, evidence on
request, never as his persona/fact, never volunteered. A disputed opinion is disclosed + flagged.
Locked → honest-empty.
"""

from __future__ import annotations

from dataclasses import dataclass

from genesys.persona.lock import can_voice
from genesys.persona.perceives import PerceivesEdge
from genesys.persona.release import ReleaseContext


@dataclass
class Voicing:
    spoken: bool
    text: str | None
    disputed: bool = False
    evidence_available: int = 0


def voice_opinion(edge: PerceivesEdge, ctx: ReleaseContext | None) -> Voicing:
    if not can_voice(ctx, edge.to):
        return Voicing(spoken=False, text=None)  # honest-empty: locked
    disputed = edge.dispute.get("status") == "disputed"
    body = f"My read — not fact, just how I see it — on {edge.to}: {edge.band}."
    if disputed:
        body = "[you've disputed this before] " + body
    return Voicing(spoken=True, text=body, disputed=disputed,
                   evidence_available=edge.strength())


def voice_or_silent(edge: PerceivesEdge, ctx: ReleaseContext | None) -> str:
    return voice_opinion(edge, ctx).text or ""
