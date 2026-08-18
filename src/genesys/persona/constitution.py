"""Constitution compiler — self-view only, perceives-excluded (spec §11, D-CON-2/3/8/10, S3).

A bounded projection of the principal's self-view: 5 categories x 3 AAAK lines, sourced from
anchors with >=1 stated sample (stated samples only). Directives, not descriptions. Takes NO
perception department — a `perceives` edge cannot enter the constitution (Fence 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from genesys.persona.anchors import has_stated_sample, stated_samples
from genesys.persona.compile_guard import assert_no_perceives

CATEGORIES = ("Values", "Communication", "Reasoning", "Collaboration", "Epistemics")
ITEMS_PER_CATEGORY = 3


@dataclass
class ConstitutionLine:
    category: str
    directive: str
    quote: str
    gr_ref: str
    stars: str = "★★★"


def format_line(line: ConstitutionLine) -> str:
    return f'{line.category}|{line.directive}|"{line.quote}"|gr:{line.gr_ref}|{line.stars}'


@dataclass
class CategorizedAnchor:
    anchor: object
    category: str
    directive: str


def compile_constitution(items: list[CategorizedAnchor]) -> list[ConstitutionLine]:
    counts: dict[str, int] = {}
    lines: list[ConstitutionLine] = []
    for item in items:
        assert_no_perceives(item.anchor)  # Fence 2 / D-CON-10: a perceives edge can never source a line
        if item.category not in CATEGORIES:
            raise ValueError(f"unknown constitution category: {item.category!r}")
        if not has_stated_sample(item.anchor):
            continue  # self-view only: no stated sample → not compile-eligible
        if counts.get(item.category, 0) >= ITEMS_PER_CATEGORY:
            continue  # one-in-one-out at the cap; ranking is the caller's job
        sample = stated_samples(item.anchor)[0]
        name = getattr(item.anchor, "name", "")
        lines.append(ConstitutionLine(category=item.category, directive=item.directive,
                                      quote=sample.quote, gr_ref=name))
        counts[item.category] = counts.get(item.category, 0) + 1
    return lines
