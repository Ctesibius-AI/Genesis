"""The inspection ladder composer (spec §3, DR-44).

Composes Tier 0 (deterministic pre-checks) -> size guard -> Tier 1 (Screen-on-raw) -> Tier 2
(Verifier) + the CS2 sampling audit, WITHOUT touching the FROZEN Supervisor deterministic spine.
Additive: the built run_gate calls this only when a LadderConfig is supplied.

Shadow mode (CS3, default ON): Tier 0 would-be hard routes are logged (journal gate-flag reason
"tier0-shadow") but route nothing; only the Screen decides. Live mode: a hard flag routes to
Tier 2 regardless of the Screen. Tier 0 hints always ride into Tier 1. The zero-facts tripwire
journals a flag (reason "tier0-tripwire") and never routes or quarantines.

Sampling audit (CS2): a random audit_rate (default 0.05) of PASSED commits is routed to the
Verifier under an INJECTED rng; the FalsePassChart tracks the Screen false-pass rate. Audits are
adjudicated by Opus (verify). Verify's remedy is applied under the FROZEN persona-remedy fence
(apply_remedy — reused verbatim). Model tiers per §12 unchanged (Sonnet Screen, Opus Verifier).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from genesis.config import get_assistant_name, get_principal
from genesis.graph.engine import GraphEdge, GraphEngine
from genesis.inspection.audit import FalsePassChart, should_audit
from genesis.inspection.screen_raw import screen_raw
from genesis.inspection.sizeguard import size_route
from genesis.inspection.tier0 import tier0_check
from genesis.journal.journal import JournalEntry, append_journal
from genesis.supervisor.gate import apply_remedy
from genesis.supervisor.verdicts import promote_created, quarantine_created
from genesis.workers.backend import LLMBackend
from genesis.workers.screen import SCREEN_PROMPT, ScreenResult
from genesis.workers.verifier import verify


@dataclass
class LadderConfig:
    shadow: bool = True                 # CS3: commission in shadow mode first (default ON)
    audit_rate: float = 0.05            # CS2: 5% of passed commits audited (config, not a literal)
    max_window_chars: int = 24000       # size guard threshold (config)
    false_pass_threshold: float = 0.10  # control-chart breach threshold on the Screen false-pass rate
    speakers: tuple[str, ...] = field(
        default_factory=lambda: (get_principal(), get_assistant_name())
    )


def run_ladder(engine: GraphEngine, data_root: Path, episode_id: str, *, window: str,
               manifest: str, created: list[GraphEdge], backend: LLMBackend, ts: str,
               ride_along: str = "", contract: str = "", cfg: LadderConfig,
               rng: random.Random, chart: FalsePassChart) -> ScreenResult:
    """Tier 0 -> size guard -> Tier 1 raw Screen -> Tier 2 (flag / hard-route / size / audit).

    Execution order (from the spec, §3):
      1. Tier 0 deterministic pre-checks (hard flags, tripwire, hints): In shadow mode,
         hard flags journal gate-flag reason "tier0-shadow" and route nothing; in live mode,
         hard flags set a flag to route to Verifier after Screen. Tripwire journals
         gate-flag reason "tier0-tripwire" and never routes or quarantines. Soft hints
         always ride into Tier 1.
      2. Size guard: if oversized window -> skip Tier 1 Screen, route straight to Tier 2 (Verifier).
      3. Tier 1 Screen-on-raw (unless size-routed): Sonnet, with Tier 0 soft hints attached.
      4. Tier 2 Verifier (Opus): invoked if Screen flagged, OR live Tier 0 hard-routed,
         OR size-routed, OR audit sampled a PASS. Apply remedy under FROZEN fence via
         apply_remedy. Journal gate-flag + gate-resolve. Audit updates chart (UPHOLD
         -> record_false_pass).
      5. Return ScreenResult preserving the Screen's verdict (the ladder adjudicates flags
         and audits internally; the caller sees what the Screen said).
    """
    # ── Tier 0 (deterministic, free, no LLM) ──────────────────────────────────────────────
    t0 = tier0_check(created, window, ride_along, speakers=set(cfg.speakers))

    # Shadow vs live hard-flag handling
    hard_route_live = False
    for f in t0.hard_flags:
        if cfg.shadow:
            # Log a would-be route but route nothing (CS3 shadow mode)
            append_journal(data_root, JournalEntry(
                ts=ts, action="gate-flag", scope=episode_id,
                target=f.edge_id, reason="tier0-shadow", author="supervisor",
            ))
        else:
            # Live mode: hard flag will route to Verifier after the Screen runs
            hard_route_live = True

    # Tripwire: non-trivial window with zero facts — advisory only, never routes
    if t0.tripwire:
        append_journal(data_root, JournalEntry(
            ts=ts, action="gate-flag", scope=episode_id,
            reason="tier0-tripwire", author="supervisor",
        ))

    # ── Size guard ────────────────────────────────────────────────────────────────────────
    route = size_route(window, max_chars=cfg.max_window_chars)

    # ── Nested _verify closure: threads backend correctly, no module global ────────────────
    def _verify(flag: str) -> str | None:
        """Run Tier 2 (Opus), apply remedy under FROZEN fence, journal gate-flag + gate-resolve.

        Returns the Verifier ruling, or None when the Verifier is UNAVAILABLE (backend raised) —
        D-FB-3(a): a suspicion the Verifier couldn't adjudicate must be QUARANTINED by the caller,
        never PASSed. The caller decides quarantine (suspicion path) vs let-pass (audit spot-check).
        """
        append_journal(data_root, JournalEntry(
            ts=ts, action="gate-flag", scope=episode_id,
            reason="ladder major", author="supervisor",
        ))
        try:
            v = verify(backend, flag=flag, raw_span=window, artifacts=manifest,
                       contract=contract or SCREEN_PROMPT)
        except Exception as exc:  # noqa: BLE001 — Verifier unavailable; signal the caller (D-FB-3a)
            append_journal(data_root, JournalEntry(
                ts=ts, action="gate-resolve", scope=episode_id,
                after="verifier-unavailable", reason=str(exc), author="supervisor",
            ))
            return None
        by_id = {e.edge_id: e for e in created}
        if v.remedy.target in by_id:
            apply_remedy(engine, data_root, by_id[v.remedy.target], v.remedy, ts=ts)
        outcome = "remedy-applied" if v.remedy.target in by_id else v.ruling.lower()
        append_journal(data_root, JournalEntry(
            ts=ts, action="gate-resolve", scope=episode_id,
            after=outcome, reason=str(v.ruling), author="supervisor",
        ))
        return v.ruling

    def _resolve_suspicion(ruling: str | None, *, where: str) -> None:
        """A suspicion path: promote the non-quarantined created edges (D-FB-3b), or — if the
        Verifier was unavailable — QUARANTINE them (D-FB-3a). Never a quiet PASS."""
        if ruling is None:
            quarantine_created(engine, data_root, created, ts=ts,
                               reason=f"verifier-unavailable ({where})")
        else:
            promote_created(engine, data_root, created, ts=ts, reason=f"verifier-resolved ({where})")

    # ── Size-routed: skip Tier 1, go straight to Tier 2 ─────────────────────────────────
    if route == "verifier":
        _resolve_suspicion(_verify(flag="size-guard: window too large to screen"), where="size-route")
        return ScreenResult(verdict="FLAG", flags=[{"code": "SIZE", "artifact": episode_id}])

    # ── Tier 1: Screen on raw window (+ Tier 0 soft hints) ───────────────────────────────
    result = screen_raw(backend, window, manifest, hints=tuple(t0.hints))

    # ── Route to Tier 2: Screen flagged (DR-30 verify-on-flag) ───────────────────────────
    if result.verdict == "FLAG":
        _resolve_suspicion(_verify(flag=str(result.flags)), where="screen-flag")
        return result

    # ── Route to Tier 2: live Tier 0 hard flag (overrides Screen PASS) ───────────────────
    if hard_route_live:
        _resolve_suspicion(_verify(flag=str([vars(f) for f in t0.hard_flags])), where="tier0-hard")
        return result

    # ── PASS path: record + maybe sampling audit (CS2) ───────────────────────────────────
    chart.record_pass()
    if should_audit(rng, rate=cfg.audit_rate):
        ruling = _verify(flag="sampling-audit of a passed commit")
        if ruling == "UPHOLD":
            chart.record_false_pass()  # Screen wrongly passed a bad commit
        # The audit is a spot-check of a PASS, NOT a suspicion: a verifier hiccup here (ruling None)
        # leaves the Screen's PASS standing. Either way, promote the non-quarantined created edges
        # (any remedy already fenced/quarantined the bad one). D-FB-3(b).
        promote_created(engine, data_root, created, ts=ts, reason="screen-pass (audited)")
    else:
        append_journal(data_root, JournalEntry(
            ts=ts, action="gate-resolve", scope=episode_id,
            after="pass", author="supervisor",
        ))
        # D-FB-3(b): a genuine Screen PASS promotes the created edges → CONFIRMED.
        promote_created(engine, data_root, created, ts=ts, reason="screen-pass")

    return result
