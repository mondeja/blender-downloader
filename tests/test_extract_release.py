"""Tests for `extract_release` function."""

import contextlib
import io
import os
import tarfile
import uuid
import zipfile

import pytest
from testing_utils import SUPPORTED_EXTENSIONS_FOR_EXTRACTION

from blender_downloader import extract_release


# TODO: test when 'root_dirnames == 1'
# TODO: test when 'root_dirnames > 1'

# TODO: MacOS '.dmg' not tested


def create_zipped_file_by_extension(tmp_path, extension, files):
    fake_release_zipped_filepath = os.path.join(
        tmp_path,
        f"{uuid.uuid4().hex}{extension}",
    )

    def files_generator():
        for fname in files:
            with open(os.path.join(tmp_path, f"{fname}.txt"), "w") as f:
                f.write(f"{fname}\n")
                filepath = f.name
            yield filepath

    if extension == ".zip":
        with zipfile.ZipFile(fake_release_zipped_filepath, "w") as zipf:
            for filepath in files_generator():
                zipf.write(filepath, os.path.relpath(filepath, tmp_path))
    elif extension in [".tar.bz2", ".tar.gz", ".tar.xz"]:
        format = extension.split(".")[2]
        with tarfile.open(fake_release_zipped_filepath, f"w:{format}") as zipf:
            for filepath in files_generator():
                zipf.add(filepath, os.path.relpath(filepath, tmp_path))
    else:
        raise NotImplementedError(
            f"Tests for extraction of files with '{extension}' are not implemented"
        )
    return fake_release_zipped_filepath


@pytest.mark.parametrize(
    "expected_files",
    (["foo"], ["foo", "bar"]),
    ids=('["foo.txt"]', '["foo.txt","bar.txt"]'),
)
@pytest.mark.parametrize(
    "extension", SUPPORTED_EXTENSIONS_FOR_EXTRACTION[4:] + [".fakeextension"]
)
@pytest.mark.parametrize("quiet", (True, False))
def test_extract_release(expected_files, extension, quiet, tmp_path):
    stderr = io.StringIO()
    if extension not in SUPPORTED_EXTENSIONS_FOR_EXTRACTION:
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(stderr):
                extract_release(f"foo{extension}", quiet=quiet)
        assert stderr.getvalue() == (
            f"File extension '{extension}' extraction not supported by"
            " '-e/--extract' command line option.\n"
        )
        return

    fake_release_zipped_filepath = create_zipped_file_by_extension(
        tmp_path,
        extension,
        expected_files,
    )

    with contextlib.redirect_stderr(stderr):
        directory_filepath = extract_release(
            fake_release_zipped_filepath,
            quiet=quiet,
        )
    assert directory_filepath == os.path.join(tmp_path, "Blender")

    output_filenames = os.listdir(directory_filepath)
    assert len(output_filenames) == len(expected_files)

    expected_filenames = [f"{f}.txt" for f in expected_files]

    for filename in output_filenames:
        assert filename in expected_filenames

        filepath = os.path.join(directory_filepath, filename)
        with open(filepath) as f:
            content = f.read()

        expected_content = filename.replace(".txt", "") + "\n"
        assert content == expected_content
    if quiet is False:
        stderr_lines = stderr.getvalue().splitlines()
        assert stderr_lines[0].startswith("Decompressing")
        assert stderr_lines[2].startswith("Extracting")
