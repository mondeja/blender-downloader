"""Available versions listing test."""

import contextlib
import io
import math
import random

import pytest

from blender_downloader import (
    MINIMUM_VERSION_SUPPPORTED,
    BlenderVersion,
    list_available_blender_versions,
)


@pytest.mark.parametrize("maximum_versions", (1, 2, random.randint(5, 10), math.inf))
@pytest.mark.parametrize("operative_system", ("linux", "windows", "macos"))
@pytest.mark.parametrize("bits", (64, 32))
@pytest.mark.parametrize("arch", (None, "arm64"))
def test_list_available_blender_versions(
    maximum_versions,
    operative_system,
    bits,
    arch,
):
    mocked_stdout = io.StringIO()
    with contextlib.redirect_stdout(mocked_stdout):
        list_available_blender_versions(maximum_versions, operative_system, bits, arch)

    prev_version, stdout_lines = (None, mocked_stdout.getvalue().splitlines())
    if maximum_versions != math.inf:
        assert len(stdout_lines) == maximum_versions

    min_version_supported = BlenderVersion(MINIMUM_VERSION_SUPPPORTED)

    for raw_version in stdout_lines:
        version = BlenderVersion(raw_version)
        assert min_version_supported <= version

        if prev_version is not None:
            assert prev_version > version
        prev_version = version
