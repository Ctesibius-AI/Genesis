"""QA console serving (spec §14 D-QA-7: localhost, no auth).

`model_to_dict` is a pure stdlib projection (testable offline). `create_app` builds the FastAPI
app with the `fastapi` import LAZY (kept out of the offline sandbox). Read-only except the one
bounded comment POST (D-QA-4).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from genesys.console.comments import add_comment, read_comments
from genesys.console.dashboard import DASHBOARD_HTML
from genesys.console.model import console_model


def model_to_dict(data_root: Path, *, now: str | None = None,
                  settings_path: Path | None = None) -> dict:
    """Convert console model to JSON-serializable dict (stdlib only).

    `now` is optional. When supplied, the deadman surface is populated.
    When omitted, `now` is read from the wall-clock HERE — the legitimate
    boundary for wall-clock reads (mirrors how hooks/cli.py resolves it).
    Existing callers that pass only `data_root` are unaffected.
    """
    if now is None:
        now = datetime.now(timezone.utc).isoformat()
    m = console_model(data_root, now=now, settings_path=settings_path)
    queue = {
        "pending": sum(1 for c in m.cards if c.extracted == "no"),
        "in_progress": sum(1 for c in m.cards if c.extracted == "in-progress"),
        "done": sum(1 for c in m.cards if c.extracted == "done"),
    }
    return {
        "cards": [{**asdict(c), "actions": [asdict(a) for a in c.actions]} for c in m.cards],
        "health": asdict(m.health) if m.health else None,
        "security": [asdict(j) for j in m.security],
        "infra": [asdict(j) for j in m.infra],
        # persona surface (view 5) removed with the persona profiler (D-GCW-6 / BT-4b)
        "deadman": asdict(m.deadman) if m.deadman is not None else None,
        "queue": queue,
    }


def create_app(data_root: Path):
    """Build FastAPI app for D-QA-7 console (localhost, no auth). FastAPI import is lazy."""
    from fastapi import FastAPI, Request  # noqa: PLC0415 — lazy: offline sandbox stays FastAPI-free
    from fastapi.responses import HTMLResponse  # noqa: PLC0415

    app = FastAPI(title="Genesys QA Console")

    @app.get("/")
    def _dashboard():
        return HTMLResponse(DASHBOARD_HTML, headers={"Cache-Control": "no-store"})

    @app.get("/api/model")
    def _model() -> dict:
        return model_to_dict(data_root)

    @app.get("/api/comments")
    def _comments() -> list[dict]:
        return [asdict(c) for c in read_comments(data_root)]

    @app.post("/api/comments")
    async def _add(request: Request) -> dict:
        c = await request.json()
        return asdict(add_comment(
            data_root, ts=c["ts"], episode_id=c["episode_id"],
            card_section=c["card_section"], comment=c["comment"],
            verdict_hint=c.get("verdict_hint"),
        ))

    return app
