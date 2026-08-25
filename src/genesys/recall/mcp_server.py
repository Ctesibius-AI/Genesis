"""Recall MCP server (design §4.2 / §8) — read-only, allow-list-scoped, honest-empty.

Wraps the warm `RecallDaemon` (allow-list-scoped by construction — BT-3/D-GCW-7) as MCP tools
`recall` / `expand` / `search`. Read-only: never writes, never touches the serial commit lane.
Transport per D-GCW-1 (stdio default / streamable-http opt-in). Honest-empty: the verdict's cause
(ABSENT / PENDING / DEGRADED) is always surfaced — never a bare [] (AC-R2).

`recall_response` is the pure result→dict shaping (offline-tested). `build_recall_mcp_server` is the
live binding (needs the `mcp` SDK + a warm daemon, absent offline) — lazy-imported, pragma-no-cover.
"""

from __future__ import annotations

from genesys.recall.service import RecallResult
from genesys.recall.tool import format_for_injection

RECALL_TOOL_DESCRIPTION = (
    "Retrieve memory facts related to a query. Read-only, scoped to the closed memory allow-list "
    "(never a read of the user). Returns an honest verdict (score/label/cause) — never confabulates."
)


def recall_response(result: RecallResult) -> dict:
    """Shape a RecallResult into the MCP tool response — self-describing + honest-empty.

    Always carries the verdict cause so the caller distinguishes empty (ABSENT) from queue-lag
    (PENDING) from down (DEGRADED). The allow-list scoping already happened in the service.
    """
    v = result.verdict
    verdict = None
    if v is not None:
        verdict = {"score": v.score, "label": v.label, "cause": v.cause.value}
    return {
        "served": bool(v is not None and v.served()),
        "verdict": verdict,
        "edges": [{"fact": re.edge.fact, "score": re.score, "label": re.label}
                  for re in result.edges],
        "message": format_for_injection(result),  # the honest-empty / labelled-context string
    }


def build_recall_mcp_server(daemon, *, name: str = "genesys-recall"):  # pragma: no cover - live only
    """Build the recall MCP server over the warm daemon (design §4.2) — read-only, allow-list-scoped.

    Uses `mcp.server.fastmcp.FastMCP` — the stable, documented MCP-server API on the `mcp` 1.x SDK
    line (the `[mcp]` extra pins `<2`, since the 2.x restructure removed FastMCP; live-verified
    against mcp 1.29.1, 2026-08-26). Lazy-imported: the offline sandbox has no `mcp` SDK — shape
    responses there via `recall_response()`. Tools are READ-ONLY; the honest-empty verdict
    (ABSENT/PENDING/DEGRADED) is always in the payload — never a bare [].
    """
    from mcp.server.fastmcp import FastMCP

    from genesys.recall.tier import Tier

    server = FastMCP(name)

    @server.tool(description=RECALL_TOOL_DESCRIPTION)
    def recall(query: str, top_n: int = 5) -> dict:
        return recall_response(daemon.serve_search(query, Tier.FULL, top_n=top_n))

    @server.tool(description="Three-channel honest-empty search over memory (allow-list-scoped).")
    def search(query: str, top_n: int = 5) -> dict:
        return recall_response(daemon.serve_search(query, Tier.FULL, top_n=top_n))

    @server.tool(description="Expand the 1-hop neighbourhood of a diary anchor episode.")
    def expand(anchor_episode: str) -> dict:
        return recall_response(daemon.serve_expand(anchor_episode, Tier.EPISODIC))

    return server


def main() -> None:  # pragma: no cover - live entrypoint (stdio transport, warm daemon)
    """`python -m genesys.recall.mcp_server` — the stdio recall MCP server (D-GCW-1 default)."""
    import os

    from genesys.recall.daemon import build_recall_daemon

    daemon = build_recall_daemon(os.environ.get("GENESYS_DATA_ROOT", "."),
                                 db_path=os.environ.get("GENESYS_DB_PATH"))
    build_recall_mcp_server(daemon).run()  # stdio by default; http is the D-GCW-1 opt-in


if __name__ == "__main__":  # pragma: no cover
    main()
