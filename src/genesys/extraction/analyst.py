"""Analyst — prepares an episode for extraction (spec §4.4).

Reads the OWNED raw span (DR-24), indexed by the ledger entry, and pairs it with the entry's
fast-path summary (the jot). The Grapher then feeds the content to the engine; the summary is
the jot the gate screens against.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesys.episode.ownedfile import read_episode_file
from genesys.ledger.entry import LedgerEntry
from genesys.wal.annotate import annotation_record, is_annotation
from genesys.wal.window import read_window


@dataclass
class Episode:
    episode_id: str
    content: str
    jot: str


def prepare_episode(data_root: Path, entry: LedgerEntry) -> Episode:
    if is_annotation(entry):
        # F5 (§2.3): cut the window from the memory-grade record instead of an episode file.
        content = read_window(annotation_record(entry), data_root,
                              entry.provenance.span_start, entry.provenance.span_end)
        return Episode(episode_id=entry.entry_id, content=content, jot=entry.summary)
    # Legacy copied-episode path (pre-F5) — unchanged.
    _header, body = read_episode_file(data_root, entry.provenance.episode_id)
    return Episode(episode_id=entry.entry_id, content=body, jot=entry.summary)
