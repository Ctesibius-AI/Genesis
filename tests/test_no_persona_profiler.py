"""BT-4b / AC-P1: the persona profiler is absent from the OSS build.

A fresh install writes zero `perceives` edges and ships no profiler modules (D-GCW-6). Persona
return = a separate gated opt-in module (roadmap), never dormant code in the default build.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import genesys


def test_persona_package_is_gone():
    for mod in ("genesys.persona", "genesys.persona.department", "genesys.persona.perceives",
                "genesys.console.persona"):
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{mod} should have been removed from the OSS build (BT-4b)")


def test_no_perceives_write_path_in_source():
    src = Path(genesys.__file__).parent
    offenders = []
    for p in src.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        if "PerceptionDepartment" in text or "perceives_anchor" in text or "class_=\"perceives\"" in text:
            offenders.append(p.name)
    assert offenders == [], f"persona-profiler write path still present in: {offenders}"
