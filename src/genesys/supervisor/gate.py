"""Two-stage quality gate — DR-30 (spec §4.4, §8.5).

Screen every commit; on a `major` flag run the Verifier on the raw; apply its remedy under
the FENCE (§8.5): corrected_text never rewrites a Trait/Value persona anchor — there the remedy
is restricted to quarantine + re-extraction. Recommends via workers; writes via P3.1 ops + journal.
"""

from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import GraphEdge, GraphEngine, Verdict
from genesys.journal.journal import JournalEntry, append_journal
from genesys.supervisor.verdicts import set_verdict
from genesys.workers.backend import LLMBackend
from genesys.workers.screen import SCREEN_PROMPT, ScreenResult, screen
from genesys.workers.verifier import VerifierRemedy, verify


def is_persona_anchor(edge: GraphEdge) -> bool:
    if (edge.class_ or "") in {"C3", "C4"}:
        return True
    hay = f"{edge.edge_id} {edge.fact}"
    return "Trait:" in hay or "Value:" in hay


def apply_remedy(engine: GraphEngine, data_root: Path, edge: GraphEdge, remedy: VerifierRemedy,
                 *, ts: str) -> str:
    if remedy.action == "amend" and is_persona_anchor(edge):
        set_verdict(engine, data_root, edge, Verdict.QUARANTINED, ts=ts,
                    reason="persona-remedy-fenced→quarantine")
        return "quarantined"
    if remedy.action == "amend":
        # plain/C1/C2: apply the corrected text to the fact (Supervisor-executed) + journal.
        engine.write_fact(edge.edge_id, remedy.content or edge.fact)
        append_journal(data_root, JournalEntry(ts=ts, action="gate-resolve", scope=edge.episodes[-1],
                       target=edge.edge_id, class_=edge.class_, after="amended", author="supervisor"))
        return "amended"
    return "none"


def run_gate(engine: GraphEngine, data_root: Path, episode_id: str, jot: str, manifest: str,
             created: list[GraphEdge], backend: LLMBackend, *, ts: str,
             raw_span: str = "", contract: str = "") -> ScreenResult:
    result = screen(backend, jot, manifest)
    if result.verdict != "FLAG":
        append_journal(data_root, JournalEntry(ts=ts, action="gate-resolve", scope=episode_id,
                       after="pass", author="supervisor"))
        return result
    append_journal(data_root, JournalEntry(ts=ts, action="gate-flag", scope=episode_id,
                   reason="screen major", author="supervisor"))
    # Pass the S1-S7 fidelity contract to the verifier (spec §8.5: contract = the rules
    # governing this case; for extraction flags that is the Screen's S1-S7 contract).
    fidelity_contract = contract or SCREEN_PROMPT
    v = verify(backend, flag=str(result.flags), raw_span=raw_span, artifacts=manifest, contract=fidelity_contract)
    by_id = {e.edge_id: e for e in created}
    if v.remedy.target in by_id:
        apply_remedy(engine, data_root, by_id[v.remedy.target], v.remedy, ts=ts)
    outcome = "remedy-applied" if v.remedy.target in by_id else v.ruling.lower()
    append_journal(data_root, JournalEntry(ts=ts, action="gate-resolve", scope=episode_id,
                   after=outcome, reason=str(v.ruling), author="supervisor"))
    return result
