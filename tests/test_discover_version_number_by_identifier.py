"""Test that the stable version number can be retrieved from Blender website."""

import re
import sys

from pkg_resources.extern.packaging.version import Version

from blender_downloader import discover_version_number_by_identifier


NUMBER_VERSION_REGEX = re.compile(r"\d+\.\d+\.\d+")


def test_discover_version_number_by_identifier():
    lts_version = discover_version_number_by_identifier("lts")
    sys.stdout.write("\n")
    sys.stdout.write(f"LTS release: {lts_version}\n")
    assert re.match(NUMBER_VERSION_REGEX, lts_version)

    stable_version = discover_version_number_by_identifier("stable")
    sys.stdout.write(f"Stable release: {stable_version}\n")
    assert re.match(NUMBER_VERSION_REGEX, stable_version)
    assert Version(stable_version) >= Version(lts_version)

    nightly_version = discover_version_number_by_identifier("nightly")
    sys.stdout.write(f"Nightly/daily release: {nightly_version}\n")
    assert re.match(NUMBER_VERSION_REGEX, nightly_version)
    assert Version(nightly_version) > Version(lts_version)
    assert Version(nightly_version) > Version(stable_version)

    daily_version = discover_version_number_by_identifier("daily")
    assert re.match(NUMBER_VERSION_REGEX, nightly_version)
    assert Version(nightly_version) == Version(daily_version)
