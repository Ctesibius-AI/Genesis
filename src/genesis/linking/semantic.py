"""Semantic entry linking in extraction (spec §4.6, DR-09).

Lookback + backfill over already-committed prior entries only — never waits for a future entry
(DR-09). Relatedness comes from an injected scorer. `same_topic` is symmetric (backfilled onto
the prior); `references` is directional (this entry → prior); `continues` picks the strongest
same-session prior unless save already set an explicit continuation. Ledger-authoritative.
"""

from __future__ import annotations

from pathlib import Path

from genesis.ledger.entry import LedgerEntry
from genesis.ledger.store import read_all, update
from genesis.linking.relatedness import REFERENCES_MIN, SAME_TOPIC_MIN, RelatednessScorer


def _dedup_append(target: list[str], value: str) -> bool:
    """Append value to target if not already present. Return True if appended, False if already present."""
    if value not in target:
        target.append(value)
        return True
    return False


def apply_semantic_links(data_root: Path, entry: LedgerEntry, scorer: RelatednessScorer,
                         *, lookback: int = 50) -> None:
    entries = read_all(data_root)
    prior = [e for e in entries
             if e.entry_id != entry.entry_id
             and (e.ts, e.entry_id) < (entry.ts, entry.entry_id)]
    prior.sort(key=lambda e: (e.ts, e.entry_id), reverse=True)  # most-recent first
    prior = prior[:lookback]

    best_continue: tuple[float, str] | None = None
    for p in prior:
        score = scorer.related(entry.summary, p.summary)
        if score >= SAME_TOPIC_MIN:
            _dedup_append(entry.links.same_topic, p.entry_id)
            prior_mutated = _dedup_append(p.links.same_topic, entry.entry_id)
            if prior_mutated:
                update(data_root, p)
            if p.links.session_id == entry.links.session_id:
                if best_continue is None or score > best_continue[0]:
                    best_continue = (score, p.entry_id)
        elif score >= REFERENCES_MIN:
            _dedup_append(entry.links.references, p.entry_id)

    if entry.links.continues is None and best_continue is not None:
        entry.links.continues = best_continue[1]
