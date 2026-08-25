"""Genesis recall — on-demand retrieval tier (spec §4.7b, DR-33).

A READ-ONLY, optional-by-construction layer over the built Graphiti graph (P3): DR-33
three-channel honest-empty + allow-list-scoped expand/search + code-inserted diary anchors +
a Daimon-driven recall tool. The read-guard is the CLOSED allow-list (BT-3/D-GCW-7); recall is
DECOUPLED from the persona layer (BT-4/AC-P2 — no persona import, no ReleaseContext). Recall down
⇒ degrade to diary + honest-empty; it never touches capture or the serial commit lane (D-SUP-7).
"""

from __future__ import annotations
