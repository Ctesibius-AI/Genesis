"""Tests for QA console server (spec §14 D-QA-7).

- `model_to_dict` is pure stdlib; serializable without FastAPI.
- `create_app` lazy-imports FastAPI (not at module load).
"""

from __future__ import annotations

import sys
from pathlib import Path

from genesys.console.server import model_to_dict


def test_model_to_dict_is_json_serializable(tmp_path: Path):
    import json
    d = model_to_dict(tmp_path)
    json.dumps(d)  # must not raise
    assert set(d) >= {"cards", "health", "security", "infra", "persona"}


def test_model_to_dict_persona_has_four_sub_surfaces(tmp_path: Path):
    import json
    d = model_to_dict(tmp_path)
    p = d["persona"]
    assert set(p) >= {"fact_conflicts", "perceived", "discussion_requests", "release_log"}
    json.dumps(p)  # must not raise (dataclasses fully projected to dicts)


def test_server_module_does_not_import_fastapi_at_top_level():
    import genesys.console.server  # noqa: F401
    assert "fastapi" not in sys.modules
