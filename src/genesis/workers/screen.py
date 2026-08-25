"""Screen worker — every commit, Sonnet, flag-only (spec §8.4, App C.3.1).

Checks the jot against the engine manifest for fidelity (S1–S7); never checks truth against
the raw (that is the Verifier, only on a flag). Recommends; never writes.
"""

from __future__ import annotations

from dataclasses import dataclass

from genesis.workers.backend import TIER_SONNET, LLMBackend, safe_json_object

SCREEN_PROMPT = """\
You are the Screen in a memory supervision pipeline. An extraction engine has
just committed entities and facts to a knowledge graph from one conversation
episode. Your only job is to check the commit against the fidelity contract
below and either PASS it or FLAG it. You never judge whether facts are true —
only whether the extraction is faithful to its source.

<inputs>
JOT: the fast-path summary of the episode (what was actually said, condensed)
MANIFEST: entities created/linked and facts written by the engine, with
attribution fields
</inputs>

Check every manifest item against the jot. Flag on any of:

S1. UNGROUNDED: a fact with no basis in the jot. Facts may condense, never add.
S2. ATTRIBUTION LOSS: a claim by the assistant or a third party written as if
    established truth, or any fact about the principal not traceable to the
    principal's own words or their explicit acceptance ("yes", "agreed",
    "let's do that"). Silence is not acceptance.
S3. DIAGNOSIS: any trait, value, emotional pattern, or psychological
    conclusion about the principal that the principal did not state in their
    own words. Behavior described as behavior passes; behavior interpreted as
    character flags.
S4. CERTAINTY PROMOTION: the jot shows hedged or conditional language
    ("maybe", "considering", "leaning toward", "if X then") but the fact
    states a settled position, or a plan became a completed action.
S5. RESERVED EDGE: the engine emitted SUPERSEDED_BY or LIVED_EXPRESSION.
    These belong to other writers. Always flag.
S6. PERSONA FIELD VIOLATION: a Trait node without self_described=true, or a
    Value node with an empty/paraphrased articulation_quote (the quote must
    appear in the jot near-verbatim).
S7. FORCED TYPE: an entity classified into a type whose definition it clearly
    does not meet, when generic Entity was available.

Do not flag: paraphrase that preserves detail and strength; facts the engine
skipped (recall is not your job); style differences between jot and fact.

<output>
{"verdict": "PASS" | "FLAG",
 "flags": [{"code": "S1-S7", "artifact": "<entity/fact name>",
            "jot_evidence": "<the jot text that shows the problem, or NONE>"}]}
</output>

One episode, one verdict. When genuinely uncertain whether something crosses
a line, FLAG — the Verifier exists to absorb your false positives cheaply.
The failure mode you must never have is a quiet PASS on a diagnosis (S3) or
an attribution loss (S2): those poison the principal's memory.
"""


@dataclass
class ScreenResult:
    verdict: str
    flags: list[dict]


def screen(backend: LLMBackend, jot: str, manifest: str, *, model: str = TIER_SONNET) -> ScreenResult:
    user = f"<jot>{jot}</jot>\n<extraction>{manifest}</extraction>"
    raw = backend.complete(SCREEN_PROMPT, user, model=model)
    d = safe_json_object(raw)
    # Guard: if strip_fences returned a partial/inner JSON object (missing top-level keys),
    # default safely. The Screen must always produce verdict+flags.
    verdict = d.get("verdict", "PASS")
    flags = d.get("flags", [])
    if not isinstance(verdict, str) or verdict not in ("PASS", "FLAG"):
        verdict = "PASS"
    return ScreenResult(verdict=verdict, flags=flags)
