"""Fast-path save (spec §4.3, DR-03/DR-24).

"Save" = copy the raw span to an owned episode file (files-first, DR-24) → append a
ledger entry (summary + provenance + links, ``extracted: no``) → return. Cheap and
non-blocking; extraction happens later off the queue. The summary is SUPPLIED by the
caller (Daimon/the hook) — never generated here — and is scrubbed before write (DR-38).
"""

from __future__ import annotations

from pathlib import Path

from genesys.episode.ownedfile import EpisodeHeader, write_episode_file
from genesys.ids import next_episode_id
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append
from genesys.linking.structural import apply_structural_links
from genesys.save_cursor import latest_span_end_for_session
from genesys.scrub.scrubber import scrub_text


def fast_path_save(
    data_root: Path,
    *,
    raw_span: str,
    summary: str,
    session_id: str,
    speakers: list[str],
    span_start: str,
    span_end: str,
    ts: str,
    source_transcript_ref: str = "",
    prev: str | None = None,
    continues: str | None = None,
    cursor_delta: bool = False,
) -> LedgerEntry | None:
    # F4-interim (spec §2.2/§7 item 2): bank only material after this session's last
    # saved cursor. Opt-in (default OFF, backward-compatible, P5-shape). Skip-when-
    # nothing-new mirrors the backfill idempotency guard. The incoming cursor uses the
    # same rule as entry_cursor: span_end if present, else ts (empty-span_end reality).
    if cursor_delta:
        banked = latest_span_end_for_session(data_root, session_id)
        incoming = span_end or ts
        if banked and incoming <= banked:
            return None  # nothing new for this session — skip the save

    date = ts[:10]
    episode_id = next_episode_id(data_root, date)

    header = EpisodeHeader(
        episode_id=episode_id,
        session_id=session_id,
        projection="memory-grade",
        captured_at=ts,
        span_start=span_start,
        span_end=span_end,
        speakers=list(speakers),
        source_transcript_ref=source_transcript_ref,
    )
    write_episode_file(data_root, header, raw_span)  # files-first (DR-24), scrubs raw

    entry = LedgerEntry(
        entry_id=episode_id,
        ts=ts,
        summary=scrub_text(summary).text,  # DR-38: summary is a free-text surface too
        provenance=Provenance(episode_id, span_start, span_end, list(speakers)),
        links=Links(prev=prev, session_id=session_id, continues=continues),
        extracted=Extracted.NO,
        enrichment=None,
    )
    # Derive prev/next structural links when the caller has not supplied an explicit prev
    # (spec §4.6, DR-09). apply_structural_links is pure — guard is here, not there.
    if prev is None:
        apply_structural_links(data_root, entry)
    append(data_root, entry)
    return entry
