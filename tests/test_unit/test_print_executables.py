"""Tests for 'print_executables' function."""

import contextlib
import functools
import io
import os
import tempfile

import pytest

from blender_downloader import print_executables


@contextlib.contextmanager
def create_temporary_directory_by_os(operative_system, create_executables=True):
    with tempfile.TemporaryDirectory() as tmpdir:
        if operative_system == 'linux':
            if create_executables:
                open(os.path.join(tmpdir, 'blender'), 'a').close()
                os.mkdir(os.path.join(tmpdir, 'bin'))
                open(os.path.join(tmpdir, 'bin', 'pythonX.Ym'), 'a').close()
        elif operative_system == 'windows':
            if create_executables:
                open(os.path.join(tmpdir, 'blender.exe'), 'a').close()
                os.mkdir(os.path.join(tmpdir, 'bin'))
                open(os.path.join(tmpdir, 'bin', 'foo.exe'), 'a').close()
        else:  # operative_system == "macos":  # noqa: PLR5501
            if create_executables:
                os.mkdir(os.path.join(tmpdir, 'MacOS'))
                open(os.path.join(tmpdir, 'MacOS', 'Blender'), 'a').close()
                os.mkdir(os.path.join(tmpdir, 'bin'))
                open(os.path.join(tmpdir, 'bin', 'pythonX.Ym'), 'a').close()
        yield tmpdir


@pytest.mark.parametrize('operative_system', ('linux', 'macos', 'windows'))
@pytest.mark.parametrize('print_blender_executable', (True, False))
@pytest.mark.parametrize('print_python_executable', (True, False))
@pytest.mark.parametrize(
    'create_executables',
    (
        True,
        False,  # in this case create executables and error must be printed
    ),
)
def test_print_executables(
    operative_system,
    print_blender_executable,
    print_python_executable,
    create_executables,
):
    # number of lines expected in output
    n_expected_output_lines = len(
        list(
            filter(
                lambda x: x is True,
                [print_blender_executable, print_python_executable],
            ),
        ),
    )

    with create_temporary_directory_by_os(
        operative_system,
        create_executables=create_executables,
    ) as dir_filepath:
        print_executables_pt = functools.partial(
            print_executables,
            dir_filepath,
            operative_system,
            print_blender_executable,
            print_python_executable,
        )

        mocked_stdout, mocked_stderr = (io.StringIO(), io.StringIO())
        with contextlib.redirect_stdout(mocked_stdout), (
            contextlib.redirect_stderr(mocked_stderr)
        ):
            if not create_executables and n_expected_output_lines > 0:
                with pytest.raises(SystemExit):
                    print_executables_pt()
            else:
                print_executables_pt()

        fd = mocked_stderr if not create_executables else mocked_stdout
        output_lines = fd.getvalue().splitlines()
        assert len(output_lines) == n_expected_output_lines
