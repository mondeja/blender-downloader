"""Available versions listing test."""

import contextlib
import io
import math
import random

import pytest

from blender_downloader import (
    MINIMUM_VERSION_SUPPPORTED,
    list_available_blender_versions,
)


class BlenderVersion:
    """Lazy comparison of Blender versions."""

    def __init__(self, raw):
        self.raw = raw

        self.version_info = list()
        for i, partial in enumerate(raw.split(".")):
            if i > 1:
                for ch in partial:
                    if ch.isalpha():
                        break
                    self.version_info.append(int(ch))
            else:
                num = ""
                for ch in partial:
                    if ch.isalpha():
                        break
                    num += ch
                self.version_info.append(int(num))

    def __lt__(self, other):
        return other.version_info >= self.version_info

    def __repr__(self):
        return self.raw


@pytest.mark.parametrize("arch", (None, "arm64"))
@pytest.mark.parametrize("maximum_versions", (1, 2, random.randint(5, 10), math.inf))
@pytest.mark.parametrize("operative_system", ("linux", "windows", "macos"))
@pytest.mark.parametrize("bits", (64, 32))
def test_list_available_blender_versions(
    maximum_versions, operative_system, bits, arch
):
    mocked_stdout = io.StringIO()
    with contextlib.redirect_stdout(mocked_stdout):
        list_available_blender_versions(maximum_versions, operative_system, bits, arch)

    prev_version, stdout_lines = (None, mocked_stdout.getvalue().splitlines())
    if maximum_versions != math.inf:
        assert len(stdout_lines) == maximum_versions

    min_version_supported = BlenderVersion(MINIMUM_VERSION_SUPPPORTED)

    for i, raw_version in enumerate(stdout_lines):
        version = BlenderVersion(raw_version)
        assert min_version_supported < version

        if i > 2:  # first version is the stable one
            if prev_version is not None:
                assert version < prev_version
        prev_version = version
