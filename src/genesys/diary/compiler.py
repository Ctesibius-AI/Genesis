"""Diary compiler (spec §4.7, App E). Gather inputs -> synthesize -> budget -> Briefing.

Regenerated whole on each call (DR-10); never persisted as truth. The synthesis prompt is
the ratified E.5 text. tasks/open_questions default empty until their sources (P5/P3) exist.
"""

from __future__ import annotations

from pathlib import Path

from genesys.diary.backend import DiaryBackend
from genesys.diary.briefing import Briefing, enforce_budget, parse_briefing
from genesys.diary.inputs import DiaryInputs, gather_ledger_items

DIARY_PROMPT = """\
You are the Diary Compiler for a memory system. You regenerate a short,
sectioned briefing of the principal's recent work from the inputs below —
nothing else. You are a summarizer of provided material, not a knower; if an
input is empty, its section is empty. Never invent, never infer character,
never speculate.

<inputs>
LEDGER: recent activity-log entries (each: summary, links, extracted-status,
        [unverified] flag). Prefer the enriched summary; if extracted != done,
        keep the [unverified] marker on that item verbatim.
TASKS: current commitments with due dates and urgency (already ranked).
OPEN_QUESTIONS: queued C1/C2 clarifications the Supervisor wants surfaced.
</inputs>

Produce exactly these sections, in this order, omitting a section only if its
input is empty:
1. TOP OF MIND — the few threads most worth resuming, judged by recency,
   open-loops, and relevance to active work. No decay math; your judgment.
2. OPEN THREADS — active projects/discussions not yet concluded; one line each.
3. COMMITMENTS — deadlines and promises, most urgent first (as given). Never
   omit a dated commitment, even an old one.
4. RECENT SESSIONS — a short chronological digest of the last few sessions,
   newest first, for continuity.
5. OPEN QUESTIONS — the queued clarifications, phrased plainly, at most a few,
   never stacked. Only what is in OPEN_QUESTIONS. Never add trait/character
   questions of your own.

Rules:
- Ground strictly in the inputs. An empty input is an empty section — say
  nothing rather than fill it.
- Keep [unverified] markers exactly where the input carries them.
- Never include the principal's traits/values, your impressions of him, or any
  "soul"/persona content. This briefing is about work, not who he is.
- Stay within the token budget; if you must cut, cut from TOP OF MIND and
  RECENT SESSIONS first, never from COMMITMENTS or OPEN QUESTIONS.
- Plain language, past/present tense, no preamble, no sign-off.
"""


def compile_diary(
    data_root: Path,
    *,
    now_iso: str,
    backend: DiaryBackend,
    window_days: int = 6,
    cap_tokens: int = 4000,
    tasks: list[dict] | None = None,
    open_questions: list[dict] | None = None,
) -> Briefing:
    inputs = DiaryInputs(
        ledger=gather_ledger_items(data_root, now_iso, window_days),
        tasks=list(tasks or []),
        open_questions=list(open_questions or []),
    )
    briefing = parse_briefing(backend.synthesize(DIARY_PROMPT, inputs))
    return enforce_budget(briefing, cap_tokens)
