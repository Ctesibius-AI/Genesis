"""Alignment (Clerk diff) + persona journal emitters (spec §9.2, §8.7).

A deterministic per-anchor diff of the self-view vs the perceived-view → aligned | divergent +
magnitude; recomputed at Day-Close; NEVER a verdict (§9.2). Emits the existing persona journal
types (`perceive`, `perceive-dispute`, `alignment`) — no new action types (D-OBS-1 already maps
them to the persona console view).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesys.journal.journal import JournalEntry, append_journal
from genesys.persona.perceives import PerceivesEdge


@dataclass
class Alignment:
    """Per-anchor Clerk diff result: aligned status + magnitude.

    Never a verdict (§9.2) — just structural observation of whether both records
    speak to the anchor and by how much they differ.
    """
    anchor: str
    status: str  # "aligned" | "divergent"
    magnitude: int


def align(anchor_name: str, self_stated: list, perceived: PerceivesEdge | None) -> Alignment:
    """Deterministic per-anchor Clerk diff.

    Args:
        anchor_name: The anchor being compared.
        self_stated: List of stated samples from the self-view.
        perceived: The PerceivesEdge from the perceived-view, or None if not recorded.

    Returns:
        Alignment with status ("aligned" iff both sides non-empty, else "divergent")
        and magnitude = abs(self_n - perc_n).
    """
    self_n = len(self_stated)
    perc_n = perceived.strength() if perceived is not None else 0
    status = "aligned" if (self_n > 0 and perc_n > 0) else "divergent"
    return Alignment(anchor=anchor_name, status=status, magnitude=abs(self_n - perc_n))


def journal_perceive(data_root: Path, *, ts: str, anchor: str, episode: str,
                     reason: str | None = None) -> None:
    """Emit a perceive journal entry.

    Args:
        data_root: The data root directory for journal storage.
        ts: Timestamp (RFC3339, e.g. "2026-08-17T10:00:00Z").
        anchor: The anchor being perceived (e.g. "Trait:rigor").
        episode: The episode being inferred from (e.g. "EP-1").
        reason: Optional reason for the perception.
    """
    append_journal(data_root, JournalEntry(
        ts=ts, action="perceive", scope=episode, target=anchor, class_="C3",
        author="inferred", reason=reason))


def journal_dispute(data_root: Path, *, ts: str, anchor: str, reason_ref: str) -> None:
    """Emit a perceive-dispute journal entry.

    Args:
        data_root: The data root directory for journal storage.
        ts: Timestamp (RFC3339).
        anchor: The anchor being disputed.
        reason_ref: Reference to the reason for the dispute.
    """
    append_journal(data_root, JournalEntry(
        ts=ts, action="perceive-dispute", scope=anchor, target=anchor,
        author="principal", reason=reason_ref))


def journal_alignment(data_root: Path, *, ts: str, day: str, alignment: Alignment) -> None:
    """Emit an alignment journal entry.

    Args:
        data_root: The data root directory for journal storage.
        ts: Timestamp (RFC3339).
        day: The day being closed (e.g. "2026-08-17").
        alignment: The Alignment result to record.
    """
    append_journal(data_root, JournalEntry(
        ts=ts, action="alignment", scope=day, target=alignment.anchor,
        after={"status": alignment.status, "magnitude": alignment.magnitude},
        author="supervisor"))
