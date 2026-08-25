"""SessionStart injection + PreCompact flush LOGIC (spec §4.8, DR-08/DR-14).

Logic only — installs no live Claude Code hook and reads no real transcript (that is a
separate owner-gated deploy step). SessionStart injection returns the diary text a hook
would emit as additionalContext. The PreCompact flush does the SYNCHRONOUS DURABLE part
first (fast_path_save) and only then a best-effort diary regen that can never break durability
(F-GENESYS-17).
"""

from __future__ import annotations

from pathlib import Path

from genesys.diary.backend import DiaryBackend
from genesys.diary.compiler import compile_diary
from genesys.recall.anchors import attach_anchors, resolve_anchors
from genesys.save import fast_path_save


def session_start_context(data_root: Path, *, now_iso: str, backend: DiaryBackend, **compile_kw) -> str:
    # BT-10 / AC-A1 (§4.5): attach code-inserted anchors post-synthesis so recall `expand` can
    # resolve a briefing anchor's episodes. attach_anchors marks ONLY anchors whose name already
    # appears in the briefing (safe — never LLM-emitted ids), and returns a new Briefing (DR-10).
    briefing = compile_diary(data_root, now_iso=now_iso, backend=backend, **compile_kw)
    briefing = attach_anchors(briefing, resolve_anchors(data_root))
    return briefing.render()


def precompact_flush(
    data_root: Path,
    *,
    raw_span: str,
    summary: str,
    session_id: str,
    speakers: list[str],
    span_start: str,
    span_end: str,
    ts: str,
    backend: DiaryBackend | None = None,
    source_transcript_ref: str = "",
) -> dict:
    # 1) SYNCHRONOUS DURABLE PART — must complete; this is the flush's guarantee.
    entry = fast_path_save(
        data_root, raw_span=raw_span, summary=summary, session_id=session_id,
        speakers=speakers, span_start=span_start, span_end=span_end, ts=ts,
        source_transcript_ref=source_transcript_ref,
    )
    # 2) BEST-EFFORT diary regen — never allowed to break the durable flush (DR-14).
    diary_ok = False
    if backend is not None:
        try:
            compile_diary(data_root, now_iso=ts, backend=backend)
            diary_ok = True
        except Exception:
            diary_ok = False
    return {"entry_id": entry.entry_id, "diary_regenerated": diary_ok}
