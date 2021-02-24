"""Test for `download_release` function."""

import contextlib
import io
import os
import tempfile

import pytest

from blender_downloader import download_release


def test_download_release():
    """This test downloads a file located in Blender repositories. Really
    is not a release zipped file, but a MD5 hash text file. Anyways, serves
    for the purposes of the `download_release` function.
    """
    filename = "blender-2.91.2.md5"
    expected_filepath = os.path.join(tempfile.gettempdir(), filename)
    if os.path.isfile(expected_filepath):
        os.remove(expected_filepath)

    url = f"https://download.blender.org/release/Blender2.91/{filename}"

    # download the file, output doesn't exists
    downloaded_filepath = download_release(
        url,
        tempfile.gettempdir(),
        quiet=True,
    )

    assert os.path.isfile(expected_filepath)
    assert downloaded_filepath == expected_filepath
    with open(expected_filepath) as f:
        linux_release_hash = f.readlines()[0].split(" ")[0]
    assert linux_release_hash == "6d7efa1a76ce095d5afdf00a64ad2e7a"

    # download the file, output exists
    mocked_stderr = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stderr(mocked_stderr):
            download_release(
                url,
                tempfile.gettempdir(),
                quiet=True,
            )
    assert mocked_stderr.getvalue().startswith(
        f"There is already a file named as '{filename}' in the directory in"
        " which Blender will be downloaded."
    )

    os.remove(expected_filepath)
