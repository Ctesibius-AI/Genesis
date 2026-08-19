"""Size guard (spec §3/§4): a window too large to screen routes straight to the Verifier."""
from __future__ import annotations

from genesys.inspection.sizeguard import size_route


def test_small_window_is_screenable():
    assert size_route("a short window", max_chars=1000) == "screen"


def test_oversized_window_routes_to_the_verifier():
    big = "x" * 5000
    assert size_route(big, max_chars=1000) == "verifier"


def test_boundary_is_inclusive_of_max_chars():
    assert size_route("y" * 1000, max_chars=1000) == "screen"
    assert size_route("y" * 1001, max_chars=1000) == "verifier"


def test_empty_window_is_screen_not_oversized():
    assert size_route("", max_chars=1000) == "screen"
