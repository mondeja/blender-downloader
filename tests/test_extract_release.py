"""Tests for `extract_release` function."""

import contextlib
import io
import os
import shutil
import tarfile
import tempfile
import uuid
import zipfile

import pytest

from blender_downloader import (
    SUPPORTED_FILETYPES_EXTRACTION,
    extract_release,
    get_running_os,
)


# NOTE: MacOS '.dmg' not tested
EXTENSIONS = [".zip", ".tar.bz2", ".tar.gz", ".tar.xz", ".fakeextension"]


def create_zipped_file_by_extension(extension):
    fake_release_zipped_filepath = os.path.join(
        tempfile.gettempdir(),
        f"{uuid.uuid4().hex}{extension}",
    )

    _f = tempfile.NamedTemporaryFile("w", delete=False)
    _f.write("foo\n")
    f = open(_f.name)
    _f.close()

    if extension == ".zip":
        with zipfile.ZipFile(fake_release_zipped_filepath, "w") as zipf:
            zipf.write(f.name)
    elif extension in [".tar.bz2", ".tar.gz", ".tar.xz"]:
        format = extension.split(".")[2]
        with tarfile.open(fake_release_zipped_filepath, f"w:{format}") as zipf:
            zipf.add(f.name)
    return (fake_release_zipped_filepath, f)


@pytest.mark.skipif(
    get_running_os() == "macos",
    reason="MacOS extraction not covered by 'test_extract_release' test.",
)
@pytest.mark.parametrize("extension", EXTENSIONS)
@pytest.mark.parametrize("quiet", (True, False))
def test_extract_release(extension, quiet):
    if quiet is True:
        return
    mocked_stderr = io.StringIO()
    if ("." + extension.split(".")[-1]) not in SUPPORTED_FILETYPES_EXTRACTION:
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(mocked_stderr):
                extract_release(f"foo{extension}", quiet=quiet)
        assert mocked_stderr.getvalue() == (
            f"Blender compressed release file 'foo{extension}' extraction is"
            " not supported by blender-downloader.\n"
        )
        return

    fake_release_zipped_filepath, content_f = create_zipped_file_by_extension(
        extension,
    )

    attempt = 0
    while attempt < 2:
        with contextlib.redirect_stderr(mocked_stderr):
            directory_filepath = extract_release(
                fake_release_zipped_filepath,
                quiet=quiet,
            )

        assert os.path.isdir(directory_filepath)
        files = os.listdir(directory_filepath)
        if len(files) > 1:
            shutil.rmtree(directory_filepath)
            attempt += 1
        else:
            break
    assert len(files) == 1
    with open(os.path.join(directory_filepath, files[0])) as f:
        assert f.read() == content_f.read()

    if quiet is False:
        stderr_lines = mocked_stderr.getvalue().splitlines()
        fake_release_zipped_filename = os.path.basename(fake_release_zipped_filepath)
        assert stderr_lines[0] == f"Decompressing '{fake_release_zipped_filename}'..."
        assert stderr_lines[2].startswith(
            f"Extracting '{fake_release_zipped_filename}': ",
        )

    # cleanup
    os.remove(fake_release_zipped_filepath)
    content_f.close()
    os.remove(content_f.name)
    shutil.rmtree(directory_filepath)
