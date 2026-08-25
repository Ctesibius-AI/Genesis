"""BT-10 / AC-A1: diary compile attaches briefing anchors so recall `expand` can resolve them.

The wiring: session_start_context runs resolve_anchors + attach_anchors post-synthesis, so a
briefing anchor whose name already appears in the diary carries its episode ids (expand-resolvable).
"""
from __future__ import annotations

from pathlib import Path

from genesis.diary.backend import FakeBackend
from genesis.diary.hooks import session_start_context
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append

NOW = "2026-08-17T12:00:00+00:00"


def _entry(eid, ts, summary, **links):
    return LedgerEntry(entry_id=eid, ts=ts, summary=summary,
                       provenance=Provenance(eid, "0", "1", ["the principal"]),
                       links=Links(session_id="s1", **links), extracted=Extracted.DONE)


def test_session_start_attaches_expandable_anchors(tmp_path: Path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00+00:00", "old plan"))
    append(tmp_path, _entry("EP-2", "2026-08-17T10:05:00+00:00", "Phrase invoicing",
                            references=["EP-1"], same_topic=["EP-1"]))
    ctx = session_start_context(tmp_path, now_iso=NOW, backend=FakeBackend())
    assert "ANCHORS" in ctx                     # the anchor section was attached post-synthesis
    assert "Phrase invoicing" in ctx
    assert "EP-1" in ctx and "EP-2" in ctx      # anchor → its episodes, so expand can resolve it


def test_session_start_without_links_has_no_anchors(tmp_path: Path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00+00:00", "solo note"))
    ctx = session_start_context(tmp_path, now_iso=NOW, backend=FakeBackend())
    assert "ANCHORS" not in ctx  # nothing to anchor
