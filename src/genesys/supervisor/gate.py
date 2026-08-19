"""Two-stage quality gate — DR-30 (spec §4.4, §8.5).

Screen every commit; on a `major` flag run the Verifier on the raw; apply its remedy under
the FENCE (§8.5): corrected_text never rewrites a Trait/Value persona anchor — there the remedy
is restricted to quarantine + re-extraction. Recommends via workers; writes via P3.1 ops + journal.
"""

from __future__ import annotations

import random
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
             raw_span: str = "", contract: str = "",
             ladder: LadderConfig | None = None, window: str | None = None,  # type: ignore[name-defined]
             ride_along: str = "", rng: random.Random | None = None,
             chart: FalsePassChart | None = None) -> ScreenResult:  # type: ignore[name-defined]
    # Opt-in inspection ladder (spec §3, DR-44). Default OFF: the built jot-Screen path below runs
    # verbatim. The jot is NOT passed to the ladder (§4 — jot is a display label, not the reference).
    # Lazy imports break the gate ↔ ladder circular dependency (ladder.py imports apply_remedy
    # from gate.py at module level; gate imports ladder only on the hot path).
    if ladder is not None:
        from genesys.inspection.audit import FalsePassChart  # noqa: PLC0415
        from genesys.inspection.ladder import run_ladder  # noqa: PLC0415
        return run_ladder(
            engine, data_root, episode_id,
            window=(window if window is not None else raw_span),
            manifest=manifest, created=created, backend=backend, ts=ts,
            ride_along=ride_along, contract=contract, cfg=ladder,
            rng=(rng or random.Random()), chart=(chart or FalsePassChart()),
        )
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
