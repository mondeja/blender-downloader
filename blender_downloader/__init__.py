#!/usr/bin/env python

"""blender-downloader"""

import argparse
import os
import re
import shutil
import sys
import tarfile
import zipfile
from functools import lru_cache
from urllib.request import Request, urlopen, urlsplit

from pkg_resources import parse_version
from pkg_resources.extern.packaging.version import Version
from tqdm import tqdm


__description__ = "Multiplatorm Blender portable release downloader script."
__version__ = "0.0.1"

QUIET = False

SCRIPT_NEW_ISSUE_URL = "https://github.com/mondeja/blender-downloader/issues/new"
NIGHTLY_VERSION_NAMES = ("beta", "alpha", "nightly", "daily")
MINIMUM_VERSION_SUPPPORTED = "2.64"
SUPPORTED_FILETYPES_EXTRACTION = [".bz2", ".gz", ".xz", ".zip", ".dmg"]


def get_running_os():
    if sys.platform == "darwin":
        return "macos"
    return "windows" if "win" in sys.platform else "linux"


@lru_cache(64)
def GET(url):
    return urlopen(Request(url)).read().decode("utf-8")


def build_parser():
    parser = argparse.ArgumentParser(description=__description__)
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s " + __version__,
        help="Show program version number and exit.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Don't print any output. Pass this option if you want to suppress"
        " the progress bar.",
    )
    parser.add_argument(
        "blender_version",
        nargs=1,
        metavar="BLENDER_VERSION",
        help="Blender version to download. Could be a version number,"
        " 'stable', 'nightly', 'daily', 'beta' or 'alpha', being"
        " 'nightly' the same as 'beta' and 'daily' the same as 'alpha'."
        f" The minium version supported is {MINIMUM_VERSION_SUPPPORTED}.",
    )
    parser.add_argument(
        "-d",
        "--output-directory",
        dest="output_directory",
        default=os.getcwd,
        help="Directory where the downloaded release file will be located."
        " As default, the current working directory.",
    )
    parser.add_argument(
        "-e",
        "--extract",
        dest="extract",
        action="store_true",
        help="Extract the content of the zipped release file. If this option"
        " is passed, the content of the release file will be extracted"
        " in the same repository as '--output-directory' value argument.",
    )
    parser.add_argument(
        "-p",
        "--print-executables",
        dest="print_executables",
        action="store_true",
        help="If this option is passed, the executables of Blender and the"
        " Python interpreter included with Blender will be printed"
        " to the standard output.",
    )
    parser.add_argument(
        "--os",
        "--operative-system",
        dest="operative_system",
        default=get_running_os,
        help="Operative system for which the Blender version downloaded will"
        " be built. By default, the operative system selected will that"
        " currently running in your machine. Could be either 'windows',"
        " 'macos' or 'linux'.",
    )
    parser.add_argument(
        "--bits",
        dest="bits",
        default=64 if sys.maxsize > 2 ** 32 else 32,
        type=int,
        help="Operative system bits. Keep in mind that Blender v2.80 was the"
        " latest release with support operative systems wit 32 bits.",
    )
    return parser


def parse_args(args):
    parser = build_parser()
    if "-h" in args or "--help" in args:
        parser.print_help()
        sys.exit(0)
    opts = parser.parse_args(args)

    # operative system by function and assert that is valid
    if hasattr(opts.operative_system, "__call__"):
        opts.operative_system = opts.operative_system()
    if opts.operative_system not in ["linux", "macos", "windows"]:
        sys.stderr.write(
            f"Invalid operative system '{opts.operative_system}'. Must be"
            " either 'linux', 'macos' or 'windows'.\n"
        )
        sys.exit(1)

    # parse version
    opts.blender_version = opts.blender_version[0]
    if opts.blender_version == "stable":
        opts.blender_version = get_stable_release_version_number()

    # parse output directory
    if hasattr(opts.output_directory, "__call__"):
        opts.output_directory = opts.output_directory()

    # define '--quiet' option globally
    global QUIET
    QUIET = opts.quiet

    # assert compatible bits
    if opts.bits == 32 and (
        opts.blender_version in NIGHTLY_VERSION_NAMES
        or parse_version(opts.blender_version) > Version("2.80")
    ):
        sys.stderr.write(
            "The latest Blender version with support for 32 bits systems is"
            " v2.80. Please, specify a more recent version of Blender.\n"
        )
        sys.exit(1)
    elif opts.bits not in [64, 32]:
        sys.stderr.write(f"Invalid bits '{opts.bits}'. Must be either 32 or 64.\n")
        sys.exit(1)

    return opts


def get_stable_release_version_number():
    """Retrieves the latest Blender stable release version number from their
    website.
    """
    res = GET("https://www.blender.org/download/")[8000:15000]
    try:
        return re.search(r"blender-(\d+\.\d+\.\d+)-", res).group(1)
    except AttributeError as err:
        if "'NoneType' object has no attribute 'group'" in str(err):
            sys.stderr.write(
                "Failed to obtain the stable release version of Blender.\n"
                " Please, report this issue using the next URL:"
                f" {SCRIPT_NEW_ISSUE_URL}\n"
            )
            sys.exit(1)
        raise err


def get_nightly_release_download_url(blender_version, operative_system):
    """Retrieves the download URL for a nightly release version of Blender.

    Parameters
    ----------

    blender_version : str
      Version for which the URL will be discovered. Could be either 'nightly',
      'daily', 'beta' or 'alpha'.

    operative_system : str
      Operative system correspondent to the release.
    """
    blender_version = {"nightly": "beta", "daily": "alpha"}.get(
        blender_version, blender_version
    )

    res = GET("https://builder.blender.org/download/")[500:-8000]

    versions_data = None
    for line in res.splitlines():
        if "/download/blender-" in line:
            versions_data = line.split("<")
            break

    _os_index, _needed_os_index = (0, {"beta": 1, "alpha": 2}[blender_version])
    download_path = None
    for dataline in versions_data:
        if f"os {operative_system}" in dataline:
            _os_index += 1
            continue
        if _os_index == _needed_os_index and dataline.startswith('a href="/'):
            download_path = dataline.split('"')[1]
            break

    return f"https://builder.blender.org{download_path}"


def get_legacy_release_download_url(blender_version, operative_system, bits):
    """Retrieves the download URL for a specifc release version of Blender.

    Parameters
    ----------

    blender_version : str
      Version for which the URL will be discovered. Should be a valid version
      of Blender, otherwise shows an error an the script will exit with 1 code.

    operative_system : str
      Operative system correspondent to the release.

    bits : str
      Number of bits of the system for the release.
    """
    major_minor_blender_version = re.sub(
        r"[a-zA-Z]", "", ".".join(blender_version.split(".")[:2])
    )

    if Version(major_minor_blender_version) < Version(MINIMUM_VERSION_SUPPPORTED):
        sys.stderr.write(
            "The minimum version supported by blender-downloader is"
            f" {MINIMUM_VERSION_SUPPPORTED}.\n"
        )
        sys.exit(1)

    url = "https://download.blender.org/release/"

    get_error_message = lambda: (
        f"The release '{blender_version}' can't be located in official"
        " Blender repositories.\nMake sure that you are passing a valid"
        f" version.\nYou can check all valid releases at: {url}\n\n"
        f"If you think that '{blender_version}' is a valid release and"
        " this is a problem with the downloader,\nplease, report it to"
        f" {SCRIPT_NEW_ISSUE_URL}\n"
    )

    res = GET(url)

    expected_version_path = f"Blender{major_minor_blender_version}/"
    _version_path_found = False
    for line in res.splitlines():
        if line.startswith(f'<a href="{expected_version_path}'):
            _version_path_found = True
            break

    if not _version_path_found:
        sys.stderr.write(get_error_message())
        sys.exit(1)

    major_minor_blender_release_url = f"{url}{expected_version_path}"

    res = GET(major_minor_blender_release_url)

    download_url = None

    if operative_system == "macos":
        if parse_version(major_minor_blender_version) < Version("2.65"):
            expected_os_identifier = "release-OSX"
        elif parse_version(major_minor_blender_version) < Version("2.79"):
            # previous to v2.79, macOS was identified by "OSX"
            expected_os_identifier = "OSX"
        else:
            expected_os_identifier = "macOS"
    elif operative_system == "windows":
        if parse_version(major_minor_blender_version) < Version("2.66"):
            expected_os_identifier = "release-windows"
        else:
            expected_os_identifier = operative_system
    else:
        expected_os_identifier = operative_system

    # build release filename validation function
    if operative_system == "windows":

        def valid_release_file(filename):
            # without 32 bits support
            if parse_version(major_minor_blender_version) > Version("2.80"):
                if not filename.endswith(".zip"):
                    return False
            else:
                if not filename.endswith(f"{bits}.zip"):
                    return False
            return True

    elif operative_system == "linux":
        # before v2.82, Linux releases was distributed in .tar.bz2
        if parse_version(major_minor_blender_version) < Version("2.82"):
            compressed_ext = ".tar.bz2"
        else:
            compressed_ext = ".tar.xz"

        def valid_release_file(filename):
            # without 32 bits support
            if parse_version(major_minor_blender_version) > Version("2.80"):
                if not filename.endswith(compressed_ext):
                    return False
            else:
                bits_id = "x86_64" if bits == 64 else "i686"
                if not filename.endswith(f"{bits_id}{compressed_ext}"):
                    return False
            return True

    else:  # operative_system == "macos"
        blender_Version = parse_version(major_minor_blender_version)

        if blender_Version < Version("2.79"):
            # previous to v2.79, macos release was distributed in .zip
            compressed_ext = ".zip"
        elif blender_Version == Version("2.79"):
            compressed_ext = ".tar.gz"
        else:
            compressed_ext = ".dmg"

        def valid_release_file(filename):
            if blender_Version < Version("2.72"):
                # previous to v2.72, macos release supported 32 bits
                bits_id = "x86_64" if bits == 64 else "i386"
                if not filename.endswith(f"{bits_id}{compressed_ext}"):
                    return False
            else:
                if not filename.endswith(compressed_ext):
                    return False
            return True

    for line in res.splitlines():
        if line.startswith(f'<a href="blender-{blender_version}-'):
            if line.split("-", 2)[2].startswith(expected_os_identifier):
                filename = line.split('"')[1]

                if not valid_release_file(filename):
                    continue

                download_url = f"{major_minor_blender_release_url}{filename}"
                break

    if download_url is None:
        sys.stderr.write(get_error_message())
        sys.exit(1)

    return download_url


def download_release(download_url, output_directory):
    """Downloads the release file from Blender official repository.

    Parameters
    ----------

    download_url : str
      URL of the file to download.

    output_directory : str
      Path to the directory in which the downloaded file will be stored.
    """
    # get filename of downloaded file (maybe a zip, maybe a dmg...)
    output_filename = os.path.basename(urlsplit(download_url).path)
    output_filepath = os.path.join(output_directory, output_filename)

    if os.path.isfile(output_filepath):
        sys.stderr.write(
            f"There is already a file named as '{output_filename}' in the"
            " directory in which Blender will be downloaded.\nPlease, remove"
            " the file before execute blender-downloader.\n"
        )
        sys.exit(1)

    chunksize = 8192
    downloaded_size = chunksize
    res = urlopen(Request(download_url))
    total_size_bits = int(res.info()["Content-Length"])

    progress_bar_kwargs = dict(
        total=total_size_bits,
        unit="B",
        desc=f"Downloading '{output_filename}'",
        unit_scale=True,
        unit_divisor=1000,
        miniters=1,
        disable=QUIET,
    )
    with tqdm(**progress_bar_kwargs) as progress_bar:
        data = res.read(chunksize)
        with open(output_filepath, "wb") as f:
            f.write(data)
            progress_bar.update(chunksize)
            while data:
                data = res.read(chunksize)
                f.write(data)
                progress_bar.update(chunksize)
                downloaded_size += chunksize
                if downloaded_size >= total_size_bits:
                    break
    return output_filepath


def extract_release(zipped_filepath):
    """Extracts, if needed, a Blender release file depending on their file type.

    The file to 'extract' could be a zipped file in different formats like
    '.tar.bz2', '.tar.gz', '.zip' or other file types like MacOS mountable
    disk images ('.dmg'). The purpose of this function is extract the Blender
    program from their release file, so can be used directly as will be a
    portable version.

    zipped_filepath : str
      Input filepath.

    Returns:
      str: Blender executable file path.
    """
    zipped_filename = os.path.basename(zipped_filepath)
    output_directory = os.path.abspath(os.path.dirname(zipped_filepath))
    extension = os.path.splitext(zipped_filepath)[1]

    if extension not in SUPPORTED_FILETYPES_EXTRACTION:
        sys.stderr.write(
            f"Blender compressed release file '{zipped_filename}' extraction"
            "is not supported by blender-downloader.\n"
        )
        sys.exit(1)

    # filepath of the extracted directory, don't confuse it with
    # `output_directory`, that is the directory where the file to extract
    # is located
    extracted_directory_filepath = None

    if extension == ".zip":
        with zipfile.ZipFile(zipped_filepath, "r") as f:
            namelist = f.namelist()
            extracted_directory_filepath = os.path.join(
                output_directory,
                namelist[0].split(os.sep)[0],
            )
            progress_bar_kwargs = dict(
                total=len(namelist),
                desc=f"Extracting '{zipped_filename}'",
                iterable=namelist,
                disable=QUIET,
            )
            for file in tqdm(**progress_bar_kwargs):
                f.extract(member=file, path=output_directory)
    elif extension in [".bz2", ".gz", ".xz"]:
        sys.stderr.write(f"Decompressing '{zipped_filename}'...\n")

        with tarfile.open(zipped_filepath, "r") as f:
            members = f.getmembers()

            extracted_directory_filepath = os.path.join(
                output_directory,
                members[0].name.split(os.sep)[0],
            )
            progress_bar_kwargs = dict(
                total=len(members),
                desc=f"Extracting '{zipped_filename}'",
                iterable=members,
                disable=QUIET,
            )
            for file in tqdm(**progress_bar_kwargs):
                f.extract(member=file, path=output_directory)
    else:  # extension == ".dmg":
        running_os = get_running_os()
        if running_os != "macos":
            sys.stderr.write(
                "blender-downloader can't mount MacOSX '.dmg' image files like"
                f" '{extracted_directory_filepath}' in"
                f" {running_os.capitalize()}, so you should install Blender"
                " manually.\n"
            )
            sys.exit(1)

        extracted_directory_filepath = os.path.join(
            output_directory, os.path.basename(zipped_filepath).rstrip(".dmg")
        )

        import dmglib

        with dmglib.attachedDiskImage(zipped_filepath) as mounted_dmg:
            contents_parent_dirpath = None
            for dirpath, dirnames, files in os.walk(mounted_dmg[0]):
                if (
                    os.path.basename(dirpath) == "Contents"
                    and "blender.app" in dirpath.lower()
                ):
                    contents_parent_dirpath = os.path.abspath(
                        os.path.dirname(dirpath),
                    )
                    break
            shutil.copytree(
                contents_parent_dirpath,
                extracted_directory_filepath,
            )

    return extracted_directory_filepath


def print_executables(extracted_directory_filepath, operative_system):
    """Calling this function, the filepaths of the Blender executable and the
    Python interpreter included in Blender will be printed to the standard
    output.

    Parameters
    ----------

    extracted_directory_filepath : bool
      Blender release directory.

    operative_system : str
      Operative system correspondent to the release.
    """
    # search executables by operative system
    if operative_system == "linux":
        blender_executable_filepath = os.path.join(
            extracted_directory_filepath,
            "blender",
        )

        python_executable_filepath = None
        for dirpath, dirnames, files in os.walk(extracted_directory_filepath):
            if os.path.basename(dirpath) == "bin":
                for filename in files:
                    if filename.startswith("python"):
                        python_executable_filepath = os.path.join(
                            dirpath,
                            filename,
                        )
                break
    elif operative_system == "windows":
        blender_executable_filepath = os.path.join(
            extracted_directory_filepath,
            "blender.exe",
        )

        python_executable_filepath = None
        for dirpath, dirnames, files in os.walk(extracted_directory_filepath):
            if os.path.basename(dirpath) == "bin":
                for filename in files:
                    if os.path.splitext(filename)[1] == ".exe":
                        python_executable_filepath = os.path.join(
                            dirpath,
                            filename,
                        )
                        break
                if python_executable_filepath is not None:
                    break
    else:  # operative_system == "macos"
        python_executable_filepath, blender_executable_filepath = (None, None)
        for dirpath, dirnames, files in os.walk(extracted_directory_filepath):
            dirname = os.path.basename(dirpath)
            if dirname == "bin":
                for filename in files:
                    if filename.startswith("python"):
                        python_executable_filepath = os.path.join(
                            dirpath,
                            filename,
                        )
                break
            elif dirname == "MacOS" and files[0] == "Blender":
                blender_executable_filepath = os.path.join(
                    dirpath,
                    files[0],
                )
                break

    # print executables
    error = False
    if blender_executable_filepath is None:
        sys.stderr.write("Blender executable not found.\n")
        error = True
    elif not os.path.isfile(blender_executable_filepath):
        sys.stderr.write(
            "Blender executable not found in expected path"
            f" '{blender_executable_filepath}'.\n"
        )
        error = True
    else:
        sys.stdout.write(f"{blender_executable_filepath}\n")

    if not os.path.isfile(python_executable_filepath):
        sys.stderr.write(
            "Builtin Blender Python intepreter executable filepath not found\n"
        )
        error = True
    else:
        sys.stdout.write(f"{python_executable_filepath}\n")

    if error:
        sys.exit(1)


def run(args=[]):
    opts = parse_args(args)
    if opts.blender_version in NIGHTLY_VERSION_NAMES:
        download_url = get_nightly_release_download_url(
            opts.blender_version,
            opts.operative_system,
        )
    else:
        download_url = get_legacy_release_download_url(
            opts.blender_version,
            opts.operative_system,
            opts.bits,
        )
    downloaded_release_filepath = download_release(
        download_url,
        opts.output_directory,
    )
    if opts.extract:
        extracted_directory_filepath = extract_release(
            downloaded_release_filepath,
        )

        if opts.print_executables:
            print_executables(
                extracted_directory_filepath,
                opts.operative_system,
            )

    return 0


def main():
    sys.exit(run(args=sys.argv[1:]))


if __name__ == "__main__":
    main()
