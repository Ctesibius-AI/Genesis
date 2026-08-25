"""BT-7 / D-GCW-11 close-gate: the dead `salience` flag is gone from the source tree."""
from __future__ import annotations

from pathlib import Path

import genesys


def test_no_salience_token_in_source():
    src = Path(genesys.__file__).parent
    offenders = [p.name for p in src.rglob("*.py") if "salience" in p.read_text(encoding="utf-8")]
    assert offenders == [], f"salience flag still present in: {offenders}"
