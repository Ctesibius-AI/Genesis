"""Perceives-exclusion guard (spec §11 D-CON-10, §12 S3, Fence 2).

A defensive backstop for the compile paths: a `perceives` edge (or the perception department)
must never reach the constitution or the soul compiler. Structural, not by convention.
"""

from __future__ import annotations


def is_perceives(obj: object) -> bool:
    return getattr(obj, "type", None) == "perceives"


def assert_no_perceives(items: object) -> None:
    if is_perceives(items):
        raise TypeError("perceives edge cannot enter a compile path (Fence 2 / D-CON-10)")
    if hasattr(items, "edges_for_subject"):
        raise TypeError("perception department cannot enter a compile path (Fence 2 / D-CON-10)")
    if isinstance(items, (list, tuple)):
        for it in items:
            if is_perceives(it):
                raise TypeError("perceives edge in a compile input (Fence 2 / D-CON-10)")
