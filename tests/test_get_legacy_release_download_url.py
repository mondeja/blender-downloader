"""Check if legacy versions download URLs can be retrieved from official
Blender repositories."""

import contextlib
import io
import os
import re
from urllib.request import urlsplit

import pytest
from pkg_resources import parse_version
from pkg_resources.extern.packaging.version import Version

from blender_downloader import (
    MINIMUM_VERSION_SUPPPORTED,
    SUPPORTED_FILETYPES_EXTRACTION,
    get_legacy_release_download_url,
)


@pytest.mark.parametrize(
    "blender_version",
    (
        "2.93.1",
        "2.93.0",  # change in release formats for Macos
        "2.92.0",
        "2.91.2",
        "2.83.17",
        "2.83.13",  # change in 2.83.x release formats
        "2.83.0",
        "2.82a",
        "2.81",
        "2.80",
        "2.79",
        "2.78",
        "2.77",
        "2.76",
        "2.75",
        "2.74",
        "2.73",
        "2.72",
        "2.71",
        "2.70",
        "2.69",
        "2.68",
        "2.67",
        "2.66",
        "2.65",
        "2.64",
        "2.63",
        "2.62",
        "2.61",
        "2.60",
        "2.59",
        "2.58",
        "2.57",
        # not supported version
        "0.0.1",
    ),
)
@pytest.mark.parametrize("operative_system", ("linux", "windows", "macos"))
@pytest.mark.parametrize("bits", (32, 64))
@pytest.mark.parametrize("arch", (None, "arm64", "i686"))
def test_get_legacy_release_download_url(blender_version, operative_system, bits, arch):
    blender_Version = parse_version(blender_version)

    if blender_Version < Version(MINIMUM_VERSION_SUPPPORTED):
        mocked_stderr = io.StringIO()
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(mocked_stderr):
                get_legacy_release_download_url(
                    blender_version, operative_system, bits, arch
                )
        assert mocked_stderr.getvalue() == (
            "The minimum version supported by blender-downloader is"
            f" {MINIMUM_VERSION_SUPPPORTED}.\n"
        )
        return

    url = get_legacy_release_download_url(blender_version, operative_system, bits, arch)

    expected_url_start = "https://download.blender.org/release/Blender"
    assert url.startswith(expected_url_start)

    major_minor_blender_version = re.sub(
        r"[a-zA-Z]", "", ".".join(blender_version.split(".")[:2])
    )

    def assert_url(url_end_schema):
        url_end = url_end_schema
        if "{blender_version}" in url_end:
            if "{bits}" in url_end:
                url_end = url_end.format(
                    blender_version=blender_version,
                    bits=bits,
                )
            else:
                url_end = url_end.format(blender_version=blender_version)
        if "{bits}" in url_end:
            url_end = url_end.format(bits=bits)
        assert url == (
            f"{expected_url_start}{major_minor_blender_version}/blender-{url_end}"
        )

    if operative_system == "macos":
        if blender_Version >= Version("2.93"):
            if arch in ["x64", "arm64"]:
                assert_url(f"{blender_version}-macos-{arch}.dmg")
            else:
                assert_url("{blender_version}-macos-x64.dmg")
        elif blender_Version >= Version("2.83.14") and blender_Version < Version(
            "2.84"
        ):
            assert_url("{blender_version}-macos-x64.dmg")
        elif blender_Version > Version("2.79"):
            assert_url("{blender_version}-macOS.dmg")
        elif blender_Version == Version("2.79"):
            assert_url("{blender_version}-macOS-10.6.tar.gz")
        elif blender_Version == Version("2.71"):
            if bits == 32:
                assert_url("{blender_version}-OSX_10.6-j2k-fix-i386.zip")
            else:
                assert_url("{blender_version}-OSX_10.6-j2k-fix-x86_64.zip")
        elif blender_Version < Version("2.60"):
            if bits == 32:
                assert_url("{blender_version}-OSX_10.5_i386.zip")
            else:
                assert_url("{blender_version}-OSX_10.5_x86_64.zip")
        elif blender_Version == Version("2.60"):
            if bits == 32:
                assert_url("{blender_version}-OSX_10.5_i386.zip")
            else:
                assert_url("{blender_version}-OSX_10.6_x86_64.zip")
        elif blender_Version < Version("2.64"):
            if bits == 32:
                assert_url("{blender_version}-release-OSX_10.5_i386.zip")
            else:
                assert_url("{blender_version}-release-OSX_10.5_x86_64.zip")
        elif blender_Version < Version("2.65"):
            if bits == 32:
                assert_url("{blender_version}-release-OSX_10.6_i386.zip")
            else:
                assert_url("{blender_version}-release-OSX_10.6_x86_64.zip")

        elif blender_Version < Version("2.71"):
            if bits == 32:
                assert_url("{blender_version}-OSX_10.6-i386.zip")
            else:
                assert_url("{blender_version}-OSX_10.6-x86_64.zip")
        elif blender_Version < Version("2.79"):
            assert_url("{blender_version}-OSX_10.6-x86_64.zip")
        else:  # blender_Version < Version("2.71"):
            if bits == 32:
                assert_url("{blender_version}-OSX_10.6-i386.zip")
            else:
                assert_url("{blender_version}-OSX_10.6-x86_64.zip")
    elif operative_system == "windows":
        if blender_Version >= Version("2.93"):
            assert_url("{blender_version}-windows-x64.zip")
        elif blender_Version >= Version("2.83.14") and blender_Version < Version(
            "2.84"
        ):
            assert_url("{blender_version}-windows-x64.zip")
        elif blender_Version > Version("2.80"):
            assert_url("{blender_version}-windows64.zip")
        elif blender_Version > Version("2.65"):
            assert_url("{blender_version}-windows{bits}.zip")
        elif blender_Version < Version("2.61"):
            assert_url("{blender_version}-windows{bits}.zip")
        else:
            assert_url("{blender_version}-release-windows{bits}.zip")
    else:  # operative_system == "linux":
        if blender_Version >= Version("2.93"):
            assert_url("{blender_version}-linux-x64.tar.xz")
        elif blender_Version >= Version("2.83.14") and blender_Version < Version(
            "2.84"
        ):
            assert_url("{blender_version}-linux-x64.tar.xz")
        elif blender_Version > Version("2.81"):
            assert_url("{blender_version}-linux64.tar.xz")
        elif blender_Version == Version("2.81"):
            assert_url("{blender_version}-linux-glibc217-x86_64.tar.bz2")
        elif blender_Version == Version("2.80"):
            if bits == 32:
                assert_url("{blender_version}-linux-glibc224-i686.tar.bz2")
            else:
                assert_url("{blender_version}-linux-glibc217-x86_64.tar.bz2")
        elif blender_Version == Version("2.79"):
            if bits == 32:
                assert_url("{blender_version}-linux-glibc219-i686.tar.bz2")
            else:
                assert_url("{blender_version}-linux-glibc219-x86_64.tar.bz2")
        elif blender_Version < Version("2.65"):
            if bits == 32:
                assert_url("{blender_version}-linux-glibc27-i686.tar.bz2")
            else:
                assert_url("{blender_version}-linux-glibc27-x86_64.tar.bz2")
        else:
            if bits == 32:
                assert_url("{blender_version}-linux-glibc211-i686.tar.bz2")
            else:
                assert_url("{blender_version}-linux-glibc211-x86_64.tar.bz2")

    # check that filetype is supported for extraction
    extension = os.path.splitext(os.path.basename(urlsplit(url).path))[1]
    assert extension in SUPPORTED_FILETYPES_EXTRACTION
