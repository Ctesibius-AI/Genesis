"""SOUL / Daimon-identity compiler — about-her, perceives-excluded (spec §12, D-CON-10, S3).

The B1 soul compile holds Daimon's own identity (about-her). It reads the self-view only and is
explicitly blind to `perceives` edges — her opinion of the principal never enters her own soul,
exactly as it never enters his constitution.
"""

from __future__ import annotations

from dataclasses import dataclass

from genesys.persona.compile_guard import assert_no_perceives

SOUL_SECTIONS = (
    "Who I Am", "How I Think", "What I Never Do",
    "Shared Language", "Philosophical Foundation", "Success Metric",
)


@dataclass
class SoulSection:
    title: str
    body: str


def compile_soul(sections: list[SoulSection]) -> list[SoulSection]:
    assert_no_perceives(sections)
    order = {name: i for i, name in enumerate(SOUL_SECTIONS)}
    for s in sections:
        if s.title not in order:
            raise ValueError(f"not an about-her soul section: {s.title!r}")
    return sorted(sections, key=lambda s: order[s.title])
