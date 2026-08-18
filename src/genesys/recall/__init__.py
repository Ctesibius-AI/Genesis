"""Genesys recall — on-demand retrieval tier (spec §4.7b, DR-33).

A READ-ONLY, optional-by-construction layer over the built Graphiti graph (P3) and persona
fence (P6): DR-33 three-channel honest-empty + persona-fenced expand/search + code-inserted
diary anchors + a Daimon-driven recall tool. Recall down ⇒ degrade to diary + honest-empty;
it never touches capture or the serial commit lane (design §6/§7, D-SUP-7).
"""

from __future__ import annotations
