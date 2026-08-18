from __future__ import annotations

from pathlib import Path

from genesys.episode.ownedfile import EpisodeHeader, write_episode_file
from genesys.extraction.cli import main
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append, read_all


def _seed(data: Path):
    eid = "EP-2026-08-17.0001"
    write_episode_file(data, EpisodeHeader(episode_id=eid, session_id="s", projection="memory-grade",
                       captured_at="t", span_start="a", span_end="b", speakers=["the principal"],
                       source_transcript_ref="r"), "raw body")
    append(data, LedgerEntry(entry_id=eid, ts="2026-08-17T10:00:00+00:00", summary="jot",
           provenance=Provenance(eid, "a", "b", ["the principal"]), links=Links(session_id="s")))


def test_cli_status_runs(tmp_path: Path, capsys):
    data = tmp_path / "d"; data.mkdir(); _seed(data)
    assert main(["status", "--data", str(data)]) == 0
    assert "1" in capsys.readouterr().out  # one queued


def test_cli_run_drains_with_fakes(tmp_path: Path):
    data = tmp_path / "d"; data.mkdir(); _seed(data)
    assert main(["run", "--data", str(data), "--now", "2026-08-17T10:05:00+00:00"]) == 0
    assert all(e.extracted is Extracted.DONE for e in read_all(data))
