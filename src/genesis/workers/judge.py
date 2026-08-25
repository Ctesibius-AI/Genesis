"""Invalidation Judge — Sonnet, on an engine invalidation, recommend-only (spec §8.4, App C.3.2).

Decides whether an engine closure was EARNED under the convergent-evidence doctrine or must be
REVERTed (sub-threshold). Class-aware. Recommends; the Supervisor reverts (P3.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from genesis.workers.backend import TIER_SONNET, LLMBackend, safe_json_object

JUDGE_PROMPT = """\
You are the Invalidation Judge. The extraction engine has closed a previously
established fact (marked it invalid) because a new episode appears to
contradict it. Your job is to decide whether that closure was EARNED under
the convergent-evidence doctrine, or must be recommended for revert. You do
not decide which fact is true. You decide whether the evidence for change
meets the bar.

<inputs>
CLOSED_FACT: the fact that was invalidated, with its full provenance (every
episode that asserted it, with dates and attribution)
NEW_EVIDENCE: the new fact and the episode text that produced it
FACT_CLASS: C1 (state) | C2 (preference) | C3 (trait) | C4 (identity/value)
PRIOR_CONTEST: any existing evidence_against entries on the closed fact
</inputs>

Step 1 — Count independent occurrences of the contradicting claim.
Two occurrences are INDEPENDENT only if they are distinct real-world events:
- Different event-time (when it happened, not when it was said). A story told
  twice is ONE occurrence.
- Principal-sourced. Assistant suggestions, summaries, or restatements the
  principal merely accepted count as ZERO occurrences (they are proposals).
- Different elicitation. An answer and its immediate rephrasing in the same
  exchange are ONE occurrence.
Retellings, confirmations, and paraphrases collapse into their original.

Step 2 — Apply the class bar.
- C1 state: 1 independent occurrence suffices IF stated plainly by the
  principal (states change; a stated change is presumptively real). Flag for
  ask-window instead when the statement is hedged.
- C2 preference: 2 independent occurrences, OR 1 explicit stated update
  ("I don't like X anymore"). Revealed behavior counts here and only here.
- C3 trait: never closed by episode evidence. Traits are distributions —
  recommend REVERT and route the observation to the trait's evidence set.
- C4 identity/value: never closed by episode evidence. Explicit renunciation
  by the principal goes to the ask-window, not to silent closure. REVERT.

Step 3 — Check for the stated-update fast path: if the principal explicitly
corrected the old fact in their own words ("actually it's Y now", "we changed
that"), the closure is EARNED regardless of count. (Doctrine: stated updates
apply immediately, `author: stated` — DR-27 v3, parent spec v1.4.)

<output>
{"recommendation": "EARNED" | "REVERT",
 "independent_occurrences": N,
 "occurrence_analysis": [{"episode": "...", "counts_because" | "collapsed_because": "..."}],
 "stated_update": true | false,
 "ask_window": true | false,
 "reasoning": "<= 3 sentences"}
</output>

Bias to REVERT under uncertainty: a wrongly reverted closure costs one journal
entry and re-closes on the next real occurrence; a wrongly accepted closure
silently rewrites the principal's memory.
"""


@dataclass
class JudgeResult:
    recommendation: str
    independent_occurrences: int
    occurrence_analysis: list[dict] = field(default_factory=list)
    stated_update: bool = False
    ask_window: bool = False
    reasoning: str = ""


def invalidation_judge(backend: LLMBackend, closed_fact: str, new_evidence: str, fact_class: str,
                       prior_contest: str = "", *, model: str = TIER_SONNET) -> JudgeResult:
    user = (f"CLOSED_FACT: {closed_fact}\nNEW_EVIDENCE: {new_evidence}\n"
            f"FACT_CLASS: {fact_class}\nPRIOR_CONTEST: {prior_contest}")
    raw = backend.complete(JUDGE_PROMPT, user, model=model)
    d = safe_json_object(raw)
    # Guard: recommendation is required; default REVERT (conservative: don't close without ruling).
    recommendation = d.get("recommendation", "REVERT")
    if not isinstance(recommendation, str) or recommendation not in ("EARNED", "REVERT"):
        recommendation = "REVERT"
    return JudgeResult(
        recommendation=recommendation, independent_occurrences=d.get("independent_occurrences", 0),
        occurrence_analysis=d.get("occurrence_analysis", []),
        stated_update=d.get("stated_update", False), ask_window=d.get("ask_window", False),
        reasoning=d.get("reasoning", ""),
    )
