"""Briefing model + deterministic token-budget enforcement (spec App E.4).

Tokens are estimated as ceil(chars/4) — good enough for a "≤ ~4k" budget guard with no
tokenizer dependency. Overflow drops WHOLE low-priority sections in a fixed order and
NEVER drops Commitments or Open Questions (deadlines never buried; clarifications never lost).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from genesis.diary.backend import SECTION_HEADERS

# Sections overflow may drop, highest-priority-to-keep last (dropped left-to-right).
_DROP_ORDER = ("TOP OF MIND", "RECENT SESSIONS", "OPEN THREADS")
_NEVER_DROP = ("COMMITMENTS", "OPEN QUESTIONS")


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


@dataclass
class Briefing:
    sections: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        parts = [f"## {h}\n{self.sections[h]}" for h in SECTION_HEADERS if h in self.sections]
        return "\n\n".join(parts)


def parse_briefing(text: str) -> Briefing:
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        header = stripped[3:].strip() if stripped.startswith("## ") else None
        if header in SECTION_HEADERS:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = header, []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return Briefing(sections=sections)


def enforce_budget(b: Briefing, cap_tokens: int) -> Briefing:
    kept = dict(b.sections)
    for header in _DROP_ORDER:
        if estimate_tokens(Briefing(kept).render()) <= cap_tokens:
            break
        kept.pop(header, None)
    return Briefing(sections=kept)
