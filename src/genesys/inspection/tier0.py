"""Tier 0 — deterministic pre-checks (spec §3; CS3). Pure, offline, NO LLM, NO I/O.

Hard checks (near-certain, rare) -> route straight to Tier 2 (only when live):
  - a number/date token in a fact ABSENT from the window + the 3-episode ride-along context;
  - attribution to a party NOT in the configured speaker set.
Soft signal (vulnerable to legitimate pronoun resolution) -> attach as a HINT for Tier 1, never
route: an entity name in the fact not found verbatim in window + ride-along.
Completeness tripwire (free): a non-trivial window with ZERO extracted facts -> flag.

A Tier 0 hit NEVER auto-quarantines — quarantine stays the Supervisor deterministic spine's job.
The ride-along context is passed in as an opaque string (Tier 0 does not reach into the FROZEN
grapher/transfer port; the caller supplies the 3-episode ride-along span text).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from genesys.graph.engine import GraphEdge

# A "non-trivial" window is one with at least this many whitespace tokens; below it, a
# zero-facts window is legitimately empty (a greeting, an ack) and must not trip the wire.
TRIVIAL_WORDS = 20

# number/date-shaped tokens: ISO dates first (so 2026-05-31 is one token, not three numbers),
# then decimals/integers with thousands separators, then bare clock/percent digits.
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
# "<Name> said/told/asked/replied/wrote/noted" — a capitalized name in an attribution position.
_ATTRIBUTION = re.compile(
    r"\b([A-Z][a-zA-Z]+)\s+(?:said|told|asked|replied|wrote|noted|claimed|stated|argued)\b"
)

# Stopwords: pronouns, articles/demonstratives, days, months.
# A candidate name matching any of these is NOT treated as a party — they are function/temporal
# words, not person names, and allowing them would swamp false-alarm measurements in CS3 shadow mode.
_ATTRIBUTION_STOPWORDS: frozenset[str] = frozenset({
    # Pronouns
    "He", "She", "It", "We", "They", "You", "I", "Him", "Her", "Them", "Us",
    # Articles / demonstratives
    "The", "A", "An", "This", "That", "These", "Those", "There", "Here",
    # Days
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    # Months
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
})


@dataclass(frozen=True)
class Tier0Flag:
    edge_id: str
    kind: str   # "number_date_absent" | "non_participant"
    token: str


@dataclass(frozen=True)
class Tier0Hint:
    edge_id: str
    entity: str


@dataclass
class Tier0Result:
    hard_flags: list[Tier0Flag] = field(default_factory=list)
    hints: list[Tier0Hint] = field(default_factory=list)
    tripwire: bool = False

    def routes(self) -> bool:
        """True iff a hard flag would route to Tier 2 (only acted on when live, not shadow)."""
        return bool(self.hard_flags)


def number_date_tokens(text: str) -> set[str]:
    """Extract number- and date-shaped tokens (dates whole; then numbers/percent/clock digits)."""
    dates = set(_ISO_DATE.findall(text))
    # Remove the date substrings before scanning numbers so 2026-05-31 doesn't yield 2026/05/31.
    stripped = _ISO_DATE.sub(" ", text)
    numbers = {m.replace(",", "") for m in _NUMBER.findall(stripped)}
    return dates | numbers


def tier0_check(created: list[GraphEdge], window: str, ride_along: str, *,
                speakers: set[str], entities: dict[str, list[str]] | None = None) -> Tier0Result:
    """Run the four Tier 0 checks over the created edges against the window + ride-along."""
    corpus = f"{window}\n{ride_along}"
    corpus_tokens = number_date_tokens(corpus)
    result = Tier0Result()

    for edge in created:
        fact = edge.fact or ""
        # (1) number/date-token hard check
        for tok in number_date_tokens(fact):
            if tok not in corpus_tokens:
                result.hard_flags.append(
                    Tier0Flag(edge_id=edge.edge_id, kind="number_date_absent", token=tok))
        # (2) attribution-to-a-non-participant hard check
        # Skip any candidate name in _ATTRIBUTION_STOPWORDS — those are function/temporal words,
        # not party names (e.g. "He said", "Monday told", "The project noted" are not attributions
        # to a party and must not produce a non_participant flag).
        for name in _ATTRIBUTION.findall(fact):
            if name in _ATTRIBUTION_STOPWORDS:
                continue
            if name not in speakers:
                result.hard_flags.append(
                    Tier0Flag(edge_id=edge.edge_id, kind="non_participant", token=name))
        # (3) entity-not-verbatim soft check -> hint (never routes)
        # Use word-boundary match so "Gene" is not considered present when corpus has "Genesys".
        for name in (entities or {}).get(edge.edge_id, []):
            pattern = r"\b" + re.escape(name) + r"\b"
            if not re.search(pattern, corpus):
                result.hints.append(Tier0Hint(edge_id=edge.edge_id, entity=name))

    # (4) completeness tripwire: a non-trivial window with zero facts.
    if not created and len(window.split()) >= TRIVIAL_WORDS:
        result.tripwire = True

    return result
