"""Tier 1 — the Screen, grounded on the RAW WINDOW (spec §3/§4; DR-30 revised, DR-44).

The Screen's reference swaps from the jot (F2 — a jot can't ground a session) to the raw window
itself, cut via Plan 2's read_window(). It compares the manifest against the actual conversation
text (+ Tier 0 soft hints), flag-only, cheap, always-on, Sonnet (§12 tier FROZEN). It NEVER
screens against a machine summary of the raw (circularity ban — that summary is the demoted jot).

The built workers.screen.screen(backend, jot, ...) is LEFT INTACT for legacy callers; this is a
sibling entry point on the ladder path. Same S1-S7 codes, same two-stage flag-only economics.
"""

from __future__ import annotations

from genesis.inspection.tier0 import Tier0Hint
from genesis.workers.backend import TIER_SONNET, LLMBackend, safe_json_object
from genesis.workers.screen import ScreenResult

SCREEN_RAW_PROMPT = """\
You are the Screen in a memory supervision pipeline. An extraction engine has
just committed entities and facts to a knowledge graph from one conversation
window. Your only job is to check the commit against the fidelity contract
below and either PASS it or FLAG it. You never judge whether facts are true —
only whether the extraction is faithful to its source.

<inputs>
RAW_WINDOW: the actual conversation text for this window (the real source — NOT
a summary). Ground every judgment in THIS text.
MANIFEST: entities created/linked and facts written by the engine, with
attribution fields.
HINTS: optional deterministic Tier 0 soft signals (e.g. an entity name not found
verbatim in the window). Hints are leads, not verdicts — a legitimate pronoun
resolution can explain a hint. Weigh them; do not treat a hint as proof.
</inputs>

NEVER screen against a machine summary of the raw window — that is circular. The
RAW_WINDOW above is the source of truth for grounding.

Check every manifest item against the RAW_WINDOW. Flag on any of:

S1. UNGROUNDED: a fact with no basis in the raw window. Facts may condense,
    never add.
S2. ATTRIBUTION LOSS: a claim by the assistant or a third party written as if
    established truth, or any fact about the principal not traceable to the
    principal's own words or their explicit acceptance ("yes", "agreed",
    "let's do that"). Silence is not acceptance.
S3. DIAGNOSIS: any trait, value, emotional pattern, or psychological
    conclusion about the principal that the principal did not state in their
    own words. Behavior described as behavior passes; behavior interpreted as
    character flags.
S4. CERTAINTY PROMOTION: the raw window shows hedged or conditional language
    ("maybe", "considering", "leaning toward", "if X then") but the fact
    states a settled position, or a plan became a completed action.
S5. RESERVED EDGE: the engine emitted SUPERSEDED_BY or LIVED_EXPRESSION.
    These belong to other writers. Always flag.
S6. PERSONA FIELD VIOLATION: a Trait node without self_described=true, or a
    Value node with an empty/paraphrased articulation_quote (the quote must
    appear in the raw window near-verbatim).
S7. FORCED TYPE: an entity classified into a type whose definition it clearly
    does not meet, when generic Entity was available.

Do not flag: paraphrase that preserves detail and strength; facts the engine
skipped (recall is not your job); style differences between the window and a fact.

<output>
{"verdict": "PASS" | "FLAG",
 "flags": [{"code": "S1-S7", "artifact": "<entity/fact name>",
            "window_evidence": "<the raw-window text that shows the problem, or NONE>"}]}
</output>

One window, one verdict. When genuinely uncertain whether something crosses a
line, FLAG — the Verifier exists to absorb your false positives cheaply. The
failure mode you must never have is a quiet PASS on a diagnosis (S3) or an
attribution loss (S2): those poison the principal's memory.
"""


def screen_raw(backend: LLMBackend, window: str, manifest: str, *,
               hints: tuple[Tier0Hint, ...] = (), model: str = TIER_SONNET) -> ScreenResult:
    """Screen the manifest against the raw window (+ Tier 0 hints). Flag-only, Sonnet."""
    user = f"<raw_window>{window}</raw_window>\n<extraction>{manifest}</extraction>"
    if hints:
        rendered = "; ".join(f"{h.edge_id}: entity '{h.entity}' not verbatim" for h in hints)
        user += f"\n<hints>{rendered}</hints>"
    raw = backend.complete(SCREEN_RAW_PROMPT, user, model=model)
    d = safe_json_object(raw)  # fail-closed: {} on any parse failure
    verdict = d.get("verdict", "PASS")
    flags = d.get("flags", [])
    if not isinstance(verdict, str) or verdict not in ("PASS", "FLAG"):
        verdict = "PASS"
    if not isinstance(flags, list):
        flags = []
    return ScreenResult(verdict=verdict, flags=flags)
