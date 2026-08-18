from __future__ import annotations

from pathlib import Path

from genesys.ledger.entry import Extracted
from genesys.ledger.store import read_all
from genesys.save import fast_path_save


def _save(data_root: Path, **over):
    kw = dict(
        raw_span="the principal: let's use FalkorDB Lite. Daimon: agreed.",
        summary="Decided on FalkorDB Lite for dev.",
        session_id="sess-1",
        speakers=["the principal", "Daimon"],
        span_start="2026-08-17T09:58:00+00:00",
        span_end="2026-08-17T10:00:00+00:00",
        ts="2026-08-17T10:00:00+00:00",
        source_transcript_ref="~/.claude/projects/x/sess-1.jsonl#0-100",
    )
    kw.update(over)
    return fast_path_save(data_root, **kw)


def test_save_writes_owned_file_and_ledger_entry(tmp_path: Path):
    entry = _save(tmp_path)
    assert entry.entry_id == "EP-2026-08-17.0001"
    assert (tmp_path / "episodes" / "EP-2026-08-17.0001.md").exists()
    assert [e.entry_id for e in read_all(tmp_path)] == ["EP-2026-08-17.0001"]


def test_saved_entry_is_queued_with_provenance(tmp_path: Path):
    entry = _save(tmp_path)
    assert entry.extracted is Extracted.NO
    assert entry.enrichment is None
    assert entry.provenance.episode_id == entry.entry_id
    assert entry.provenance.speakers == ["the principal", "Daimon"]
    assert entry.links.session_id == "sess-1"


def test_two_saves_same_day_increment_sequence(tmp_path: Path):
    _save(tmp_path)
    second = _save(tmp_path)
    assert second.entry_id == "EP-2026-08-17.0002"


def test_secret_in_summary_is_scrubbed_before_write(tmp_path: Path):
    entry = _save(tmp_path, summary="key is export API_KEY=sk-abcdef0123456789abcdef0123")
    assert "sk-abcdef0123456789abcdef0123" not in entry.summary
    assert "<redacted:secret" in entry.summary
