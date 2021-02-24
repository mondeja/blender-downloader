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

from blender_downloader import SUPPORTED_FILETYPES_EXTRACTION, extract_release


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


@pytest.mark.parametrize("extension", EXTENSIONS)
def test_extract_release(extension):
    if ("." + extension.split(".")[-1]) not in SUPPORTED_FILETYPES_EXTRACTION:
        mocked_stderr = io.StringIO()
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(mocked_stderr):
                extract_release(f"foo{extension}")
        assert mocked_stderr.getvalue() == (
            f"Blender compressed release file 'foo{extension}' extraction is"
            " not supported by blender-downloader.\n"
        )
        return

    fake_release_zipped_filepath, content_f = create_zipped_file_by_extension(
        extension,
    )
    directory_filepath = extract_release(
        fake_release_zipped_filepath,
        quiet=True,
    )

    assert os.path.isdir(directory_filepath)
    files = os.listdir(directory_filepath)
    assert len(files) == 1
    with open(os.path.join(directory_filepath, files[0])) as f:
        assert f.read() == content_f.read()

    os.remove(fake_release_zipped_filepath)
    content_f.close()
    os.remove(content_f.name)
    shutil.rmtree(directory_filepath)
