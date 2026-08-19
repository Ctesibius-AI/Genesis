"""Save = ledger annotation (spec §2.2, DR-43; F-GENESYS-03 superseded).

A save is a WINDOW into the rolling record, not a copy: a ledger entry whose provenance carries
(start_ts, end_ts) and whose episode_id is "" (no owned copy — the structural F4 dissolution).
The jot is demoted to a human-readable display label (§4). One door — save_annotation — is shared
by the automatic (hook) and manual (save tool) triggers (DR-43 "one door, two triggers").
"""

from __future__ import annotations

from pathlib import Path

from genesys.ids import next_episode_id
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append
from genesys.linking.structural import apply_structural_links
from genesys.scrub.scrubber import scrub_text
from genesys.wal.record import WalRecord


def is_annotation(entry: LedgerEntry) -> bool:
    """True iff the entry is a window annotation (no owned copy), not a legacy copied episode."""
    return entry.provenance.episode_id == "" and (entry.enrichment or {}).get("annotation") is True


def annotation_record(entry: LedgerEntry) -> WalRecord:
    """The record an annotation indexes (default memory-grade)."""
    value = (entry.enrichment or {}).get("record", WalRecord.MEMORY_GRADE.value)
    return WalRecord(value)


def save_annotation(data_root: Path, *, start_ts: str, end_ts: str, jot: str,
                    session_id: str, speakers: list[str],
                    record: WalRecord = WalRecord.MEMORY_GRADE,
                    salience: bool = False) -> LedgerEntry:
    """Append a ledger annotation over the record — a window, not a copy (DR-43)."""
    entry = LedgerEntry(
        entry_id=next_episode_id(data_root, end_ts[:10]),
        ts=end_ts,
        summary=scrub_text(jot).text,  # DR-38: the jot is a free-text label surface
        provenance=Provenance(episode_id="", span_start=start_ts, span_end=end_ts,
                              speakers=list(speakers)),
        links=Links(session_id=session_id),
        extracted=Extracted.NO,
        enrichment={"annotation": True, "record": record.value, "salience": salience},
    )
    # Mirror fast_path_save's structural-linking step (spec §4.6, DR-09): derive prev/next
    # from the immediately-prior committed entry and backfill its next in place.
    # Called BEFORE append so read_all does not yet include the current entry — same
    # ordering as fast_path_save. No explicit prev on annotations, so always applies.
    apply_structural_links(data_root, entry)
    append(data_root, entry)
    return entry
