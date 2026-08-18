"""QA-console persona surface — view 5 (spec §14, §10.1, D-QA-1).

A **read-only projection** of the grade-1 journal + the live persona records — no new source
of truth, no ingestion path (D-QA-1). Four sub-surfaces:

  (a) `fact_conflicts`      — open ask-window C1/C2 conflicts to reconcile (§10.1a). Folded from
                              `ask-queued` journal entries not yet closed by a `supersede` /
                              `contest` / `ask-resolved`. The panel is a *read* of what awaits
                              selection; the Supervisor is still the sole writer (D-RG-1a).
  (b) `perceived`           — self-view vs perceived band/spread per anchor (§10.1b, D-RG-9a).
                              Alignment (§9.2 Clerk diff) + PT-7 notice on divergence. Discuss /
                              dispute are affordances; nothing to approve or select.
  (c) `discussion_requests` — the discussion-request queue folded from the journal (§10.2).
  (d) `release_log`         — `opinion-ask/confirm/release/close`. Shows *that* a release
                              happened, its scope, and the close reason — and **NEVER the
                              opinion content** (§14, "same posture as the Security view").

## The persona fence on the console (§10.1(b) / §8.6 S2 — decision recorded)

§8.6 S2 imposes a read-time lock that filters `perceives` edges from **task / recall / compile**
reads (fail-closed unless a session `ReleaseContext` is open). The perceived-view **panel is
none of those reads**: §10.1(b) defines it explicitly as a *read of both records side-by-side
per anchor* (D-RG-9a, "the summon-is-a-read"), hosted on the localhost/no-auth QA console
(D-QA-7) whose whole purpose is the principal inspecting his two records. So the panel renders
band / spread / strength / alignment / PT-7-notice **unconditionally** — it does not consult a
`ReleaseContext`, because it is not a §8.6 voicing. Two fences the spec keeps even here:
  * the panel surfaces the *records-level projection* (band/spread/strength), never the raw
    per-episode `observation` text and never a voiced opinion; and
  * the release log renders lifecycle only, never re-exposing opinion content (§14).
This is the console's stated read-only two-record inspection surface, matching §10.1(b) exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genesys.journal.journal import JournalEntry, read_journal
from genesys.persona.alignment import align
from genesys.persona.department import PerceptionDepartment
from genesys.persona.discussion import DiscussionRequest, fold_requests
from genesys.persona.perceives import PRINCIPAL
from genesys.persona.reconcile import notice_if_divergent

# hot-lane actions that close an open ask-window conflict (the fact-conflict panel is "still open")
_CONFLICT_CLOSERS = frozenset({"supersede", "contest", "ask-resolved"})
_RELEASE_ACTIONS = ("opinion-ask", "opinion-confirm", "opinion-release", "opinion-close")


@dataclass
class FactConflict:
    """An open ask-window C1/C2 conflict awaiting the principal's selection (§10.1a)."""

    target: str
    ts: str
    class_: str | None = None


@dataclass
class PerceivedAnchor:
    """One anchor's two records side-by-side + alignment (§10.1b). A read, never a voicing."""

    anchor: str
    self_samples: int
    band: str
    spread: str
    perceived_strength: int
    alignment: str
    notice: str | None = None
    disputed: bool = False


@dataclass
class ReleaseEvent:
    """One lifecycle event of the §8.6 release machine. Scope + close reason ONLY — never content."""

    ts: str
    action: str
    anchor: str | None = None
    scope: str | None = None
    close_reason: str | None = None


@dataclass
class PersonaSurface:
    fact_conflicts: list[FactConflict] = field(default_factory=list)
    perceived: list[PerceivedAnchor] = field(default_factory=list)
    discussion_requests: list[DiscussionRequest] = field(default_factory=list)
    release_log: list[ReleaseEvent] = field(default_factory=list)


def fact_conflicts(journal: list[JournalEntry]) -> list[FactConflict]:
    """Open ask-window conflicts: an `ask-queued` whose target has no later closing action."""
    resolved: set[str] = set()
    for e in journal:
        if e.action in _CONFLICT_CLOSERS and e.target:
            resolved.add(e.target)
    out: list[FactConflict] = []
    for e in journal:
        if e.action == "ask-queued" and e.target and e.target not in resolved:
            out.append(FactConflict(target=e.target, ts=e.ts, class_=e.class_))
    return out


def perceived_panel(dept: PerceptionDepartment | None,
                    self_view: dict[str, int] | None,
                    *, subject: str = PRINCIPAL) -> list[PerceivedAnchor]:
    """Self-view vs perceived band/spread per anchor, with the §9.2 alignment + PT-7 notice."""
    if dept is None:
        return []
    self_view = self_view or {}
    rows: list[PerceivedAnchor] = []
    for edge in dept.edges_for_subject(subject):
        self_n = self_view.get(edge.to, 0)
        # align() takes the self-view stated-sample list; only its length matters here.
        alignment = align(edge.to, [None] * self_n, edge)
        rows.append(PerceivedAnchor(
            anchor=edge.to,
            self_samples=self_n,
            band=edge.band,
            spread=edge.spread,
            perceived_strength=edge.strength(),
            alignment=alignment.status,
            notice=notice_if_divergent(alignment),
            disputed=edge.dispute.get("status") == "disputed",
        ))
    return rows


def release_log(journal: list[JournalEntry]) -> list[ReleaseEvent]:
    """Fold the release machine's journal into lifecycle events — never the opinion content."""
    out: list[ReleaseEvent] = []
    for e in journal:
        if e.action not in _RELEASE_ACTIONS:
            continue
        after = e.after if isinstance(e.after, dict) else {}
        out.append(ReleaseEvent(
            ts=e.ts, action=e.action, anchor=e.target,
            scope=after.get("scope"), close_reason=e.reason,
        ))
    return out


def persona_view(data_root: Path, *, dept: PerceptionDepartment | None = None,
                 self_view: dict[str, int] | None = None,
                 subject: str = PRINCIPAL) -> PersonaSurface:
    """Compose the four persona sub-surfaces (§14 view 5). Honest-empty on empty inputs."""
    journal = read_journal(data_root)
    return PersonaSurface(
        fact_conflicts=fact_conflicts(journal),
        perceived=perceived_panel(dept, self_view, subject=subject),
        discussion_requests=sorted(fold_requests(data_root).values(),
                                    key=lambda r: r.request_id),
        release_log=release_log(journal),
    )
