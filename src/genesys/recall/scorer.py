"""DR-33 three-channel honest-empty scorer (spec §4.7a, §4.7b).

"No data" is an EARNED verdict, never a confabulated guess. Force all three channels —
semantic, keyword, graph — with per-channel visibility. Corroboration count maps to a score:
3 -> 100% (answer) · 2 -> 70% (corroborated-partial) · 1 -> 30% (weak/single-source) ·
0 -> "I don't have anything related." The 30/70 labels travel into the injected result so
Daimon serves weak/single-source honestly. Empties are weighted by CAUSE: a
just-saved-not-yet-extracted miss is PENDING (queue lag), not ABSENT — do not confabulate
around a queue lag, and do not report earned-empty when extraction simply hasn't run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Channel(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    GRAPH = "graph"


class EmptyCause(str, Enum):
    ABSENT = "absent"      # earned nothing — all three channels genuinely empty
    PENDING = "pending"    # matched a not-yet-extracted entry (queue lag), not absence
    DEGRADED = "degraded"  # recall/store is DOWN (BT-5/SUB-2, AC-R2) — down ≠ empty; never confabulate


@dataclass
class ChannelResult:
    channel: Channel
    hit: bool
    count: int = 0


_SCORE = {3: (100, "answer"), 2: (70, "corroborated-partial"),
          1: (30, "weak/single-source"), 0: (0, "honest-empty")}
_REQUIRED = {Channel.SEMANTIC, Channel.KEYWORD, Channel.GRAPH}


@dataclass
class RecallVerdict:
    score: int
    label: str
    channels: list[ChannelResult] = field(default_factory=list)
    cause: EmptyCause = EmptyCause.ABSENT

    def served(self) -> bool:
        return self.score > 0


def score_channels(results: list[ChannelResult], *,
                   cause: EmptyCause = EmptyCause.ABSENT) -> RecallVerdict:
    present = {r.channel for r in results}
    if present != _REQUIRED:
        raise ValueError(f"DR-33 forces all three channels; got {sorted(c.value for c in present)}")
    hits = sum(1 for r in results if r.hit)
    score, label = _SCORE[hits]
    return RecallVerdict(score=score, label=label, channels=list(results),
                         cause=cause if score == 0 else EmptyCause.ABSENT)
