from __future__ import annotations

from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append, read_all
from genesys.linking.structural import apply_structural_links


def _entry(eid, ts, session="s1"):
    return LedgerEntry(entry_id=eid, ts=ts, summary=f"sum {eid}",
                       provenance=Provenance(eid, "a", "b", ["the principal"]),
                       links=Links(session_id=session), extracted=Extracted.NO)


def test_prev_and_next_backfill(tmp_path):
    first = _entry("EP-1", "2026-08-17T10:00:00Z")
    append(tmp_path, first)
    second = _entry("EP-2", "2026-08-17T10:05:00Z")

    apply_structural_links(tmp_path, second)
    append(tmp_path, second)

    assert second.links.prev == "EP-1"
    reloaded = {e.entry_id: e for e in read_all(tmp_path)}
    assert reloaded["EP-1"].links.next == "EP-2"  # backfilled in place
    assert reloaded["EP-2"].links.prev == "EP-1"


def test_first_entry_has_no_prev(tmp_path):
    only = _entry("EP-1", "2026-08-17T10:00:00Z")
    apply_structural_links(tmp_path, only)
    assert only.links.prev is None


def test_prefers_same_session_prior(tmp_path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00Z", session="other"))
    append(tmp_path, _entry("EP-2", "2026-08-17T10:01:00Z", session="s1"))
    third = _entry("EP-3", "2026-08-17T10:02:00Z", session="s1")
    apply_structural_links(tmp_path, third)
    assert third.links.prev == "EP-2"  # same-session prior, not the global EP-1


def test_idempotent(tmp_path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00Z"))
    second = _entry("EP-2", "2026-08-17T10:05:00Z")
    apply_structural_links(tmp_path, second)
    apply_structural_links(tmp_path, second)  # twice
    assert second.links.prev == "EP-1"
    nexts = [e.links.next for e in read_all(tmp_path) if e.entry_id == "EP-1"]
    assert nexts == ["EP-2"]


def test_never_links_a_future_entry(tmp_path):
    """Structural linker never links or backfills a future entry (DR-09)."""
    # A future entry EP-9 with a LATER ts exists in the ledger
    append(tmp_path, _entry("EP-9", "2026-08-17T12:00:00Z"))
    # Current entry is at an EARLIER ts, with an even-earlier prior
    append(tmp_path, _entry("EP-1", "2026-08-17T10:05:00Z"))
    cur = _entry("EP-2", "2026-08-17T10:05:00Z")

    apply_structural_links(tmp_path, cur)

    # cur should link to EP-1 (the only prior), NOT to the future EP-9
    assert cur.links.prev == "EP-1"
    # EP-9 should not have its next backfilled to cur
    reloaded = {e.entry_id: e for e in read_all(tmp_path)}
    assert reloaded["EP-9"].links.next is None
