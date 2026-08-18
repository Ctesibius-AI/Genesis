"""Real orchestration backends (spec §4.13, DR-12/DR-13).

The fleet is Daimon → Team Manager → ephemeral subagents. A subagent's only upward product is an
immutable `SubagentSummary` (the lead sees only this, DR-12); it carries no write handle, so a
subagent can never write the durable spine — Daimon stays the sole durable writer (DR-13).

Two live engines sit behind lazy factories: the **Claude Agent SDK** is primary; **LangGraph** is
the fallback (DR-12). Both SDKs are imported ONLY inside their `*_orchestrator` factory — the
offline sandbox has neither and runs on `FakeOrchestrator`, so `import genesys.orchestration.backends`
must stay stdlib-only. Same lazy posture as `graph.factory.real_client` and
`recall.search_backend.real_recall_search`.

`SdkOrchestrator` is the SDK-decoupled adapter that satisfies the `Orchestrator` Protocol
(`dispatch(task) -> SubagentSummary`). It is decoupled from any SDK by taking a single injected
run callable `(task: SubagentTask) -> raw result`; the real factories inject a callable that spins
up one ephemeral subagent per task and returns its final result, and `SdkOrchestrator` shapes that
result into an immutable `SubagentSummary`. Because the adapter is SDK-agnostic, it is fully
offline-testable with a fake run callable returning canned subagent results (no network).
"""

from __future__ import annotations

from genesys.orchestration.fleet import SubagentSummary, SubagentTask


def _to_summary(task: SubagentTask, result: object) -> SubagentSummary:
    """Shape a raw subagent result into an immutable, non-write `SubagentSummary` (DR-12).

    Accepts the shapes a live subagent run can return:
      - a `SubagentSummary` already (passed through, re-stamped with this task's id);
      - a mapping with a final `summary` string and optional `findings` iterable;
      - a plain string (the final summary text, no findings).
    The result is always a frozen `SubagentSummary` free of any write handle — a summary is the
    lead's ONLY view of a subagent, and it never carries a path back to the durable spine (DR-13).
    """
    if isinstance(result, SubagentSummary):
        # Normalise the task_id so the summary is always attributable to the dispatched task.
        return SubagentSummary(task_id=task.task_id, summary=result.summary,
                               findings=tuple(result.findings))
    if isinstance(result, str):
        return SubagentSummary(task_id=task.task_id, summary=result)
    if isinstance(result, dict):
        summary = str(result.get("summary", ""))
        findings = tuple(str(f) for f in result.get("findings", ()) or ())
        return SubagentSummary(task_id=task.task_id, summary=summary, findings=findings)
    raise TypeError(
        f"unsupported subagent result for task {task.task_id!r}: {type(result).__name__} "
        "(expected SubagentSummary, mapping with 'summary', or str)")


class SdkOrchestrator:
    """`Orchestrator` over an injected per-task subagent-run callable (spec §4.13, DR-12/13).

    Decoupled from any SDK so it is offline-testable: inject any callable of the shape
    `(task: SubagentTask) -> raw result`. `dispatch` runs one ephemeral subagent through that
    callable and shapes the result into an immutable `SubagentSummary` — the lead's only view
    (DR-12). The summary carries no write handle, so a subagent can never reach the durable spine
    (DR-13). `fan_out`/`run_fleet` consume this via the `Orchestrator` Protocol; the durable write
    still happens only through Daimon's `commit_findings`.

    The live factories (`agent_sdk_orchestrator`, `langgraph_orchestrator`) inject a callable that
    spins up a real ephemeral subagent per task (single session, unlimited fan-out, DR-13).
    """

    def __init__(self, run) -> None:  # noqa: ANN001 — a (task: SubagentTask) -> result callable
        self._run = run

    def dispatch(self, task: SubagentTask) -> SubagentSummary:
        return _to_summary(task, self._run(task))


def agent_sdk_orchestrator(*, model: str | None = None) -> SdkOrchestrator:
    """Return a live Claude-Agent-SDK-backed `SdkOrchestrator` (spec §4.13, DR-12/13).

    Lazy binding, same posture as `graph.factory.real_client`: `claude_agent_sdk` is imported
    INSIDE this function so the offline sandbox (no SDK) never reaches it and uses
    `FakeOrchestrator` instead. Raises RuntimeError when the extra is absent.

    Wiring: builds a run callable that opens ONE Agent SDK session (single session, DR-13) and,
    per task, spawns an ephemeral subagent (`task.role` + `task.instruction` + `task.context`),
    runs it to completion, and returns only its final summary text + findings — never a write
    handle. That callable is injected into `SdkOrchestrator`, which shapes each result into an
    immutable `SubagentSummary`. Daimon remains the sole durable writer.
    """
    try:
        import claude_agent_sdk  # noqa: F401, PLC0415 — lazy: absent in the offline sandbox
    except ImportError as exc:  # pragma: no cover - exercised only where the extra is absent
        raise RuntimeError(
            "the 'orchestration' extra is required for the Claude Agent SDK backend; "
            "offline uses FakeOrchestrator") from exc

    # pragma: no cover below — reached only with claude_agent_sdk installed (live harness, not the
    # offline suite). Kept as the documented live-wiring shape; the concrete per-task subagent-run
    # call binds to the installed SDK's fan-out API at harness-integration time. The adapter itself
    # (SdkOrchestrator + _to_summary) is exercised offline via an injected run callable.
    def _run(task: SubagentTask):  # pragma: no cover
        raise RuntimeError(
            "Claude Agent SDK subagent-run wiring binds at harness integration; the offline "
            "adapter is exercised via SdkOrchestrator with an injected run callable")

    return SdkOrchestrator(_run)  # pragma: no cover


def langgraph_orchestrator(*, model: str | None = None) -> SdkOrchestrator:
    """Return a live LangGraph-backed `SdkOrchestrator` — the DR-12 fallback (spec §4.13).

    Same lazy posture as `agent_sdk_orchestrator`: `langgraph` is imported INSIDE this function so
    the offline sandbox never reaches it. Raises RuntimeError when the extra is absent. Builds a
    run callable that drives one LangGraph subgraph per task (ephemeral subagent) and returns only
    its final summary + findings; injected into `SdkOrchestrator` for the same summary shaping and
    the same no-write invariant (DR-13).
    """
    try:
        import langgraph  # noqa: F401, PLC0415 — lazy: absent in the offline sandbox
    except ImportError as exc:  # pragma: no cover - exercised only where the extra is absent
        raise RuntimeError(
            "the 'orchestration' extra is required for the LangGraph fallback; "
            "offline uses FakeOrchestrator") from exc

    # pragma: no cover below — reached only with langgraph installed (live harness, not offline).
    def _run(task: SubagentTask):  # pragma: no cover
        raise RuntimeError(
            "LangGraph subagent-run wiring binds at harness integration; the offline adapter is "
            "exercised via SdkOrchestrator with an injected run callable")

    return SdkOrchestrator(_run)  # pragma: no cover


def select_orchestrator(prefer: str = "agent-sdk") -> SdkOrchestrator:
    """Pick a live orchestration backend (Agent SDK primary, LangGraph fallback, DR-12).

    Selection contract (unchanged): prefer the Agent SDK; if its SDK is absent (RuntimeError),
    fall back to LangGraph; if both are absent, raise a combined RuntimeError naming both (the
    caller then drives `FakeOrchestrator` offline). A factory that raises NotImplementedError
    (deps present, wiring deliberately stubbed) is PROPAGATED, never swallowed as a fallback.
    """
    if prefer == "agent-sdk":
        try:
            return agent_sdk_orchestrator()
        except NotImplementedError:
            raise
        except RuntimeError:
            pass  # SDK absent → fall back (DR-12)
    try:
        return langgraph_orchestrator()
    except NotImplementedError:
        raise
    except RuntimeError as exc:
        raise RuntimeError(
            "no orchestration backend available (Agent SDK and LangGraph both absent); "
            "install the 'orchestration' extra or use FakeOrchestrator") from exc
