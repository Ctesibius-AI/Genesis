"""Console model + D-OBS-1 coverage (spec §14, §16).

Composes the cards + views into one read-only model. ACTION_TO_VIEW maps EVERY journal action to
a view surface — D-OBS-1 ("no journal type without a console surface") is enforced by
`obs1_uncovered()` returning empty. The persona surface (view 5) was removed from OSS with the
persona profiler (D-GCW-6 / BT-4b); its journal actions were removed from JOURNAL_ACTIONS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genesis.console.cards import Card, build_cards
from genesis.console.views import DeadmanStrip, Health, deadman_strip, health_strip, infra_view, security_view
from genesis.journal.journal import JOURNAL_ACTIONS
from genesis.journal.journal import JournalEntry

ACTION_TO_VIEW: dict[str, str] = {
    # hot lane → the report card
    "verdict": "card", "revert": "card", "supersede": "card", "contest": "card",
    "gate-flag": "card", "gate-resolve": "card", "ask-queued": "card", "ask-resolved": "card",
    "class-migrate": "card", "merge": "card", "day-processed": "day-close",
    # class auditor
    "class-audit": "card", "drift-report": "card", "fragment-merge": "card",
    "example-conflict": "card",
    # security
    "scrub": "security", "redact": "security", "redact-cascade": "security",
    # recovery
    "snapshot": "recovery", "snapshot-verify": "recovery", "restore": "recovery", "rebuild": "recovery",
    # infra
    "worker-error": "infra", "lock-violation": "infra", "stale-lock-cleared": "infra",
}


@dataclass
class ConsoleModel:
    cards: list[Card] = field(default_factory=list)
    health: Health | None = None
    security: list[JournalEntry] = field(default_factory=list)
    infra: list[JournalEntry] = field(default_factory=list)
    deadman: DeadmanStrip | None = None


def obs1_uncovered() -> set[str]:
    return set(JOURNAL_ACTIONS) - set(ACTION_TO_VIEW)


def console_model(data_root: Path, *,
                  self_view: dict[str, int] | None = None,
                  now: str | None = None, threshold_hours: float = 24.0,
                  settings_path: Path | None = None) -> ConsoleModel:
    return ConsoleModel(
        cards=build_cards(data_root),
        health=health_strip(data_root),
        security=security_view(data_root),
        infra=infra_view(data_root),
        deadman=(deadman_strip(data_root, now=now, threshold_hours=threshold_hours,
                               settings_path=settings_path) if now is not None else None),
    )
