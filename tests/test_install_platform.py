"""BT-8 / AC-PLAT1: platform-conditional default — supported→Lite, unmet→Docker or fail-loud."""
from __future__ import annotations

import pytest

from genesys.install.platform import DOCKER, STDIO_LITE, PlatformError, PlatformFacts, select_profile

SUPPORTED = PlatformFacts(system="Darwin", macos_major=15, arch="arm64", py=(3, 12), has_libomp=True)


def test_supported_floor_selects_stdio_lite():
    assert select_profile(SUPPORTED, docker_available=False) == STDIO_LITE


def test_unmet_floor_falls_back_to_docker():
    linux = PlatformFacts(system="Linux", macos_major=None, arch="x86_64", py=(3, 12), has_libomp=True)
    assert select_profile(linux, docker_available=True) == DOCKER


@pytest.mark.parametrize("facts", [
    PlatformFacts("Darwin", 14, "arm64", (3, 12), True),      # macOS too old
    PlatformFacts("Darwin", 15, "x86_64", (3, 12), True),     # not arm64
    PlatformFacts("Darwin", 15, "arm64", (3, 11), True),      # py too old
    PlatformFacts("Darwin", 15, "arm64", (3, 12), False),     # no libomp
])
def test_unmet_floor_without_docker_fails_loud_never_broken_lite(facts):
    with pytest.raises(PlatformError):
        select_profile(facts, docker_available=False)
