"""Test that the stable version number can be retrieved from Blender website."""

import re

from blender_downloader import get_stable_release_version_number


def test_get_stable_release_version_number():
    assert re.match(r"^\d+\.\d+\.\d+", get_stable_release_version_number())
