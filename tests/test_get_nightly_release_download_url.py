"""Test for retrieve nightly release versions download URLs."""

import os
from urllib.request import urlsplit

import pytest
from pkg_resources import parse_version

from blender_downloader import (
    SUPPORTED_FILETYPES_EXTRACTION,
    get_nightly_release_version_download_url,
)


@pytest.mark.parametrize("blender_versions", [["nightly", "daily"], ["beta", "alpha"]])
@pytest.mark.parametrize("operative_system", ["linux", "macos", "windows"])
def test_get_nightly_release_version_download_url(blender_versions, operative_system):
    smaller_version = None

    for blender_version in blender_versions:
        url, _ = get_nightly_release_version_download_url(
            blender_version,
            operative_system,
        )

        assert url.startswith("https://builder.blender.org/download/blender-")
        assert operative_system in url.lower()

        version = parse_version(url.split("-")[1])
        if smaller_version is None:
            smaller_version = version
        else:
            assert smaller_version <= version

        extension = os.path.splitext(os.path.basename(urlsplit(url).path))[1]
        assert extension in SUPPORTED_FILETYPES_EXTRACTION
