"""Verifier — Opus, on a flag, final (spec §8.5, App C.3.3).

Re-derives the correct judgment from the raw before comparing (the independent derivation is
what makes it a verifier, not a second opinion). Its remedy is executed verbatim by the
Supervisor — subject to the remedy fence (§8.5): corrected_text never on a Trait/Value anchor.
"""

from __future__ import annotations

from dataclasses import dataclass

from genesys.workers.backend import TIER_OPUS, LLMBackend, safe_json_object

VERIFIER_PROMPT = """\
You are the Verifier — the authoritative recheck in a memory supervision
pipeline. A cheaper worker has flagged an extraction or an invalidation
verdict. Your ruling is final and will be executed without further review.

You receive the flag, but you must NOT treat it as evidence. Re-derive the
judgment from the raw material as if seeing it first. Cheap workers are tuned
to over-flag; agreeing with them by default defeats your purpose, and so does
contrarian disagreement. The base rates are irrelevant to this one case.

<inputs>
FLAG: what the worker flagged and why
RAW_SPAN: the full episode text (not the jot — you get the source)
ARTIFACTS: the graph objects in question with full provenance
CONTRACT: the full text of the rules governing this case — the S1-S7
fidelity contract for extraction flags, or the independence rubric + class
bars for evidence flags. {CONTRACT} is a build-time substitution (same
mechanism as {PRINCIPAL}); this prompt is invalid without it injected.
</inputs>

Method:
1. From RAW_SPAN alone, state what a faithful extraction / correct evidence
   ruling would have been. Write this BEFORE looking at what was actually done.
2. Compare against ARTIFACTS. Identify every divergence.
3. Rule on the flag: UPHOLD (the flagged problem is real) or OVERRULE (the
   original action was correct).
4. If UPHOLD, specify the remedy precisely: which artifact to revert, amend,
   or annotate, and with what content. The Supervisor executes your remedy
   verbatim — vague remedies are failures.

<output>
{"ruling": "UPHOLD" | "OVERRULE",
 "independent_derivation": "<your step-1 statement>",
 "divergences": [...],
 "remedy": {"action": "revert|amend|annotate|none", "target": "...",
            "content": "..."} ,
 "reasoning": "<= 5 sentences"}
</output>

You are the most expensive component in this pipeline and the only one whose
word is final. Spend your budget on step 1 — the independent derivation is
what makes you a verifier rather than a second opinion.
"""


@dataclass
class VerifierRemedy:
    action: str
    target: str
    content: str | None


@dataclass
class VerifierResult:
    ruling: str
    remedy: VerifierRemedy
    reasoning: str


def verify(backend: LLMBackend, flag: str, raw_span: str, artifacts: str, contract: str,
           *, model: str = TIER_OPUS) -> VerifierResult:
    user = f"FLAG: {flag}\n<raw>{raw_span}</raw>\nARTIFACTS: {artifacts}\nCONTRACT: {contract}"
    raw = backend.complete(VERIFIER_PROMPT, user, model=model)
    d = safe_json_object(raw)
    rem = d.get("remedy") or {}
    # Guard: ruling is required; default OVERRULE (conservative: don't act without valid ruling).
    ruling = d.get("ruling", "OVERRULE")
    if not isinstance(ruling, str) or ruling not in ("UPHOLD", "OVERRULE"):
        ruling = "OVERRULE"
    return VerifierResult(
        ruling=ruling,
        remedy=VerifierRemedy(action=rem.get("action", "none"), target=rem.get("target", ""),
                              content=rem.get("content")),
        reasoning=d.get("reasoning", ""),
    )
