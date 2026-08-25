from __future__ import annotations

from pathlib import Path

from genesis.console.comments import Comment, add_comment, read_comments


def test_comment_is_scrubbed_before_write(tmp_path: Path):
    c = add_comment(tmp_path, ts="2026-08-17T10:00:00+00:00", episode_id="EP-1",
                    card_section="screen", comment="key is export API_KEY=sk-abcdef0123456789abcdef0123")
    assert "sk-abcdef0123456789abcdef0123" not in c.comment
    assert "<redacted:secret" in c.comment
    # persisted file also scrubbed
    assert "sk-abcdef0123456789abcdef0123" not in (tmp_path / "qa_comments.jsonl").read_text()


def test_read_comments_round_trip(tmp_path: Path):
    add_comment(tmp_path, ts="2026-08-17T10:00:00+00:00", episode_id="EP-1",
                card_section="general", comment="looks wrong", verdict_hint="wrong")
    cs = read_comments(tmp_path)
    assert len(cs) == 1 and isinstance(cs[0], Comment)
    assert cs[0].comment == "looks wrong" and cs[0].verdict_hint == "wrong"
