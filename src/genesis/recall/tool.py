"""The Daimon-driven recall tool (spec §4.7b; design §8; DR-08 — no per-turn hook).

The deep tail of the cascade: a deliberate reach-beyond-recent Daimon invokes on a touch or a
gap (γνῶθι σεαυτόν). It is an explicit tool call, NEVER an ambient pre-answer step — an ambient
per-turn touch step IS the UserPromptSubmit injection DR-08 rejected, deferred behind a DR-08
rev. Results are rendered as LABELLED DYNAMIC CONTEXT (D-CON-1/Principle 4): the caller injects
the string as context; this never writes the master prompt.
"""

from __future__ import annotations

from genesis.recall.scorer import EmptyCause
from genesis.recall.service import RecallResult, RecallService
from genesis.recall.tier import Tier


def recall_tool(service: RecallService, query: str, *, tier: Tier = Tier.FULL,
                top_n: int = 5, cause: EmptyCause = EmptyCause.ABSENT) -> RecallResult:
    return service.search(query, tier, top_n=top_n, cause=cause)


def format_for_injection(result: RecallResult) -> str:
    v = result.verdict
    if v is not None and not v.served():
        if v.cause is EmptyCause.DEGRADED:
            return "Recall: memory unavailable (recall is down) — not an empty result."
        if v.cause is EmptyCause.PENDING:
            return "Recall: matched a just-saved entry not yet extracted (queue lag) — no graph facts yet."
        return "Recall: I don't have anything related."
    header = f"Recall [{v.label} {v.score}%]:" if v is not None else "Recall:"
    lines = [header]
    for re in result.edges:
        suffix = f" {re.label}" if re.label else ""
        lines.append(f"- {re.edge.fact}{suffix}")
    return "\n".join(lines)
