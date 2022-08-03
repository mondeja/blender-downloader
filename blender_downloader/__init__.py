#!/usr/bin/env python

"""blender-downloader"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from urllib.request import Request, urlopen, urlsplit

from appdirs import user_data_dir
from diskcache import Cache, Timeout as CacheTimeout
from tqdm import tqdm


__author__ = "mondeja"
__description__ = "Multiplatform Blender portable release downloader script."
__title__ = "blender-downloader"
__version__ = "0.0.25"

QUIET = False

TEMPDIR = os.path.join(tempfile.gettempdir(), "blender-downloader")
DATA_DIR = user_data_dir(appname=__title__, appauthor=__author__, version=__version__)
CACHE = Cache(DATA_DIR)

SCRIPT_NEW_ISSUE_URL = f"https://github.com/{__author__}/{__title__}/issues/new"
BLENDER_MANUAL_VERSIONS_URL = "https://docs.blender.org/PROD/versions.json"
BLENDER_DAILY_BUILDS_URL = "https://builder.blender.org/download/daily/"
MINIMUM_VERSION_SUPPPORTED = "2.57"
NIGHLY_RELEASES_CACHE_EXPIRATION = 60 * 60 * 24  # 1 day


def removesuffix(string, suffix):  # polyfill for Python < 3.9
    if string.endswith(suffix):
        return string[: -len(suffix)]
    return string


def controlled_full_splitext(path, possible_extensions):
    extension = None
    for ext in possible_extensions:
        if path.endswith(ext):
            extension = ext
            break
    return extension


class BlenderVersion:
    """Blender versions object for easy comparations support."""

    def __init__(self, raw):
        self.raw = raw
        self.version_info = []
        self.alphas = []

        for num_or_alpha in raw.split("."):
            num = ""
            for char in num_or_alpha:
                if char.isdigit() and not self.alphas:
                    num += char
                else:
                    self.alphas.append(char)
            if num:
                self.version_info.append(int(num))
        for alpha in self.alphas:
            if alpha.isdigit():  # digits as alphas like '3' in '2.80rc3'
                self.version_info.append(int(alpha))
            else:
                self.version_info.append(ord(alpha))

    def __lt__(self, other):
        return self.version_info < other.version_info

    def __le__(self, other):
        return self.version_info <= other.version_info

    def __gt__(self, other):
        return self.version_info > other.version_info

    def __ge__(self, other):
        return self.version_info >= other.version_info

    def __eq__(self, other):
        return self.version_info == other.version_info

    def __str__(self):
        return self.raw

    def __repr__(self):
        return f'BlenderVersion("{self.raw}")'


class BlenderVersionNotFound(RuntimeError):
    pass


def get_running_os():
    if sys.platform == "darwin":
        return "macos"
    return "windows" if "win" in sys.platform else "linux"


def GET(url, expire=259200, use_cache=True):  # 3 days for expiration
    response = None
    if use_cache:
        response = CACHE.get(url)
    if response is None:
        response = urlopen(Request(url)).read()
        if use_cache:
            CACHE.set(url, response, expire=expire)
    return response.decode("utf-8")


def get_toplevel_dirnames_from_paths(paths):
    """Extracts the names of the directories in the top level
    from a set of paths constituting multiple directory trees.
    """
    toplevel_dirnames = []
    for path in paths:
        # not optimal implementation, but crossplatform for sure
        parent, _ = os.path.split(path)
        if parent:  # is not file, when is file parent == ''
            while parent:
                previous_parent = parent
                parent, _ = os.path.split(previous_parent)
            if previous_parent not in toplevel_dirnames:
                toplevel_dirnames.append(previous_parent)
    return toplevel_dirnames


def clean_other_versions_cache():
    """Remove the cache for other versions of blender-downloader
    installed. Only has sense to execute a single version, the
    latest.
    """
    caches_dir = os.path.abspath(os.path.dirname(DATA_DIR))
    for dirname in os.listdir(caches_dir):
        if dirname != __version__:
            dirpath = os.path.join(caches_dir, dirname)
            shutil.rmtree(dirpath)


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
        nargs="?",
        metavar="BLENDER_VERSION",
        help="Blender version to download. Could be a version number"
        " or one of the words 'stable' (current stable version), 'lts'"
        " (latest long term support version) and 'nightly' or 'daily'"
        " (latest development release)."
        f" The minimum version supported is {MINIMUM_VERSION_SUPPPORTED}.",
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
        " in the same repository as '--output-directory' value argument."
        " This is not supported for MacOS releases using Python3.6.",
    )
    parser.add_argument(
        "-r",
        "--remove-compressed",
        dest="remove_compressed",
        action="store_true",
        help="Remove compressed or image release file after extraction. Only"
        " takes effect if '--extract' option is passed.",
    )
    parser.add_argument(
        "-b",
        "--print-blender-executable",
        dest="print_blender_executable",
        action="store_true",
        help="If this option is passed, the location of the Blender executable"
        " will be printed to the standard output. This option must be used"
        " along with '--extract' or won't take effect.",
    )
    parser.add_argument(
        "-p",
        "--print-python-executable",
        dest="print_python_executable",
        action="store_true",
        help="If this option is passed, the location of the Python interpreter"
        " executable included With Blender will be printed to the standard"
        " output. This option must be used along with '--extract' or won't"
        " take effect.",
    )
    parser.add_argument(
        "-o",
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
        default=64 if sys.maxsize > 2**32 else 32,
        type=int,
        help="Operative system bits. Keep in mind that Blender v2.80 was the"
        " latest release with support operative systems with 32 bits.",
    )
    parser.add_argument(
        "-a",
        "--arch",
        dest="arch",
        default=None,  # depending on availability between versions
        type=str,
        help="Architecture of the build. For most versions you don't need to"
        " specify this parameter.",
    )
    parser.add_argument(
        "-l",
        "--list",
        dest="list",
        type=int,
        nargs="?",
        default=-1,
        metavar="MAX",
        help="Prints to stdout all the available Blender release versions"
        " supported by blender-downloader, ordered from newer to older"
        " versions. You can pass an optional maximum number of versions to list.",
    )
    parser.add_argument(
        "-n",
        "--no-cache",
        "--nocache",
        dest="use_cache",
        action="store_false",
        help="Don't use cache requesting Blender repositories.",
    )
    parser.add_argument(
        "-c",
        "--invalidate-cache",
        "--clear-cache",
        dest="clear_cache",
        action="store_true",
        help="Remove cache used internally by blender-downloader.",
    )
    return parser


def normalize_version(version):
    if version.count(".") == 0:
        version = f"{version.rstrip('.')}.0.0"
    elif version.count(".") == 1:
        version = f"{version.rstrip('.')}.0"
    elif version.count(".") > 2:
        version_split = version.split(".")
        version = ".".join(version_split[i] for i in range(2))
    return version.lstrip("v")


def parse_args(args):
    parser = build_parser()
    if "-h" in args or "--help" in args:
        parser.print_help()
        sys.exit(1)
    opts = parser.parse_args(args)

    # operative system by function and assert that is valid
    if hasattr(opts.operative_system, "__call__"):
        opts.operative_system = opts.operative_system()
    opts.operative_system = opts.operative_system.lower()
    if opts.operative_system not in {"linux", "macos", "windows"}:
        sys.stderr.write(
            f"Invalid operative system '{opts.operative_system}'. Must be"
            " either 'linux', 'macos' or 'windows'.\n"
        )
        sys.exit(1)

    # parse '--list' option
    if opts.list is None:
        opts.list = math.inf
    elif opts.list == -1:
        opts.list = False

    # parse version
    if opts.list is False:
        if opts.blender_version is None:
            parser.print_help()
            sys.exit(1)
        else:
            opts.blender_version = opts.blender_version.lower()

        if opts.blender_version in {"stable", "lts", "nightly", "daily"}:
            opts.blender_version = discover_version_number_by_identifier(
                opts.blender_version,
                use_cache=opts.use_cache,
            )
        elif BlenderVersion(opts.blender_version) >= BlenderVersion("2.83"):
            opts.blender_version = normalize_version(opts.blender_version)
    else:
        opts.blender_version = None

    # parse output directory
    if hasattr(opts.output_directory, "__call__"):
        opts.output_directory = opts.output_directory()

    # define '--quiet' option globally
    global QUIET
    QUIET = opts.quiet

    # compatibility between '--extract' and '--remove-compressed'
    if opts.remove_compressed and not opts.extract:
        sys.stderr.write(
            "The option '--remove-compressed' only makes sense passed along"
            " with the option '--extract'.\n"
        )
        sys.exit(1)

    # assert compatible bits
    if opts.bits == 32 and BlenderVersion(opts.blender_version) > BlenderVersion(
        "2.80"
    ):
        sys.stderr.write(
            "The latest Blender version with support for 32 bits systems is"
            " v2.80. Please, specify a more recent version of Blender.\n"
        )
        sys.exit(1)
    elif opts.bits not in [64, 32]:
        sys.stderr.write(f"Invalid bits '{opts.bits}'. Must be either 32 or 64.\n")
        sys.exit(1)

    if opts.use_cache:
        CACHE.expire()  # remove expired items from cache
        clean_other_versions_cache()

    return opts


def guess_stable_version_number_from_daily_builds_page(use_cache=True):
    """Try to get the stable Blender version from the page displayed at
    https://builder.blender.org/download/daily/

    This method has been proved unstable in the past so must not be used
    as the unique reliable source.

    use_cache : bool
      Use cache requesting Blender versions from Blender's builder page.
    """
    res = GET(
        BLENDER_DAILY_BUILDS_URL,
        expire=NIGHLY_RELEASES_CACHE_EXPIRATION,
        use_cache=use_cache,
    )

    stable_Version = None
    for line in res.split("<"):
        line = line.lower()
        if "stable" in line:
            stable_version_match = re.search(r"blender-([^-]+)", line)
            if stable_version_match is not None:
                stable_Version = BlenderVersion(stable_version_match.group(1))
                break
    return stable_Version


def discover_version_number_by_identifier(identifier, use_cache=True):
    """Discover a Blender version number given an identifier.

    Parameters
    ----------

    identifier : str
      Version identifier. Can be either 'stable', 'lts' or 'nightly'.
    use_cache : bool
      Use cache requesting Blender versions from manual.
    """
    if identifier == "stable":
        # try to get stable version from Blender's builder page
        latest_Version = guess_stable_version_number_from_daily_builds_page(
            use_cache=use_cache,
        )

        # fallback to versions JSON in documentation
        if latest_Version is None:
            versions_json = json.loads(
                GET(
                    BLENDER_MANUAL_VERSIONS_URL,
                    expire=NIGHLY_RELEASES_CACHE_EXPIRATION,
                    use_cache=use_cache,
                )
            )

            latest_Version = None
            for minor_version, version_data in versions_json.items():
                if "dev" in version_data:
                    continue

                minor_Version = BlenderVersion(minor_version)
                if latest_Version is None or minor_Version > latest_Version:
                    latest_Version = minor_Version

            if latest_Version is None:
                sys.stderr.write(
                    "Error trying to retrieve the stable release from Blender"
                    " repositories. Please, submit a report to"
                    " {SCRIPT_NEW_ISSUE_URL}\n"
                )
                sys.exit(1)
    elif identifier in {"lts", "nightly", "daily"}:
        expected_substr_in_data = "lts" if identifier == "lts" else "dev"
        latest_Version = None
        versions_json = json.loads(
            GET(
                BLENDER_MANUAL_VERSIONS_URL,
                expire=NIGHLY_RELEASES_CACHE_EXPIRATION,
                use_cache=use_cache,
            )
        )

        for minor_version, version_data in versions_json.items():
            if expected_substr_in_data not in version_data.lower():
                continue
            minor_Version = BlenderVersion(minor_version)
            if latest_Version is None or minor_Version > latest_Version:
                latest_Version = minor_Version
    else:
        sys.stderr.write(
            f"Invalid identifier '{identifier}' for Blender version. Possible"
            " values are 'stable', 'lts' and 'nightly'.\n"
        )
        sys.exit(1)
    return normalize_version(str(latest_Version))


def _build_download_repo_expected_os_identifier(
    operative_system,
    major_minor_blender_Version,
):
    if operative_system == "macos":
        if major_minor_blender_Version < BlenderVersion("2.61"):
            expected_os_identifier = "OSX"
        elif major_minor_blender_Version < BlenderVersion("2.65"):
            expected_os_identifier = "release-OSX"
        elif major_minor_blender_Version < BlenderVersion("2.79"):
            # previous to v2.79, macOS was identified by "OSX"
            expected_os_identifier = "OSX"
        else:
            expected_os_identifier = "mac"  # some macOS, other macos
    elif operative_system == "windows":
        if major_minor_blender_Version < BlenderVersion("2.61"):
            expected_os_identifier = "windows"
        elif major_minor_blender_Version < BlenderVersion("2.66"):
            expected_os_identifier = "release-windows"
        else:
            expected_os_identifier = operative_system
    else:
        expected_os_identifier = operative_system
    return expected_os_identifier


def _build_download_repo_release_file_validator(
    operative_system,
    bits,
    arch,
    major_minor_blender_Version,
):
    if operative_system == "windows":

        def valid_release_file(filename):
            # without 32 bits support
            if major_minor_blender_Version > BlenderVersion("2.80"):
                if not filename.endswith(".zip"):
                    return False
            else:
                if not filename.endswith(f"{bits}.zip"):
                    return False
            return True

    elif operative_system == "linux":
        # before v2.82, Linux releases was distributed in .tar.bz2
        if major_minor_blender_Version < BlenderVersion("2.82"):
            compressed_ext = ".tar.bz2"
        else:
            compressed_ext = ".tar.xz"

        def valid_release_file(filename):
            # without 32 bits support
            if major_minor_blender_Version > BlenderVersion("2.80"):
                if not filename.endswith(compressed_ext):
                    return False
            else:
                bits_id = "x86_64" if (bits == 64 or arch == "x86_64") else "i686"
                if not filename.endswith(f"{bits_id}{compressed_ext}"):
                    return False
            return True

    else:  # operative_system == "macos"
        if major_minor_blender_Version < BlenderVersion("2.79"):
            # previous to v2.79, macos release was distributed in .zip
            compressed_ext = ".zip"
        elif major_minor_blender_Version == BlenderVersion("2.79"):
            compressed_ext = ".tar.gz"
        else:
            compressed_ext = ".dmg"

        def valid_release_file(filename):
            if major_minor_blender_Version < BlenderVersion("2.72"):
                # previous to v2.72, macos release supported 32 bits
                bits_id = "x86_64" if (bits == 64 or arch == "x86_64") else "i386"
                if not filename.endswith(f"{bits_id}{compressed_ext}"):
                    return False
            elif major_minor_blender_Version >= BlenderVersion("2.93"):
                # from v2.93, Blender supports arm64 builds for macOS
                if arch in ["x64", "arm64"]:
                    if not filename.endswith(f"{arch}{compressed_ext}"):
                        return False
                else:
                    if not filename.endswith(f"x64{compressed_ext}"):
                        return False
            else:
                if not filename.endswith(compressed_ext):
                    return False
            return True

    return valid_release_file


def get_legacy_release_download_url(
    blender_version, operative_system, bits, arch, use_cache=True
):
    """Retrieves the download URL for a specific legacy release of Blender.

    Parameters
    ----------

    blender_version : str
      Version for which the URL will be discovered. Should be a valid version
      of Blender, otherwise shows an error an the script will exit with 1 code.

    operative_system : str
      Operative system correspondent to the release.

    bits : str
      Number of bits of the system for the release.

    arch : str
      Identifier of the architecture for which the release will be retrieved.

    use_cache : bool
      Use cache requesting Blender repositories.
    """
    major_minor_blender_version = re.sub(
        r"[a-zA-Z]", "", ".".join(blender_version.split(".")[:2])
    )
    major_minor_blender_Version = BlenderVersion(major_minor_blender_version)

    if BlenderVersion(major_minor_blender_version) < BlenderVersion(
        MINIMUM_VERSION_SUPPPORTED
    ):
        sys.stderr.write(
            "The minimum version supported by blender-downloader is"
            f" {MINIMUM_VERSION_SUPPPORTED}.\n"
        )
        sys.exit(1)

    url = "https://download.blender.org/release/"

    res = GET(url, use_cache=use_cache)

    version_path = f"Blender{major_minor_blender_version}/"
    _version_path_found = False
    for line in res.splitlines():
        if line.startswith(f'<a href="{version_path}'):
            _version_path_found = True
            break

    if not _version_path_found:
        raise BlenderVersionNotFound()

    major_minor_blender_release_url = f"{url}{version_path}"

    res = GET(major_minor_blender_release_url, use_cache=use_cache)

    download_url = None

    expected_os_identifier = _build_download_repo_expected_os_identifier(
        operative_system,
        major_minor_blender_Version,
    )

    # build release filename validation function
    valid_release_file = _build_download_repo_release_file_validator(
        operative_system,
        bits,
        arch,
        major_minor_blender_Version,
    )

    for line in res.splitlines():
        if not line.startswith(f'<a href="blender-{blender_version}-'):
            continue

        if not line.split("-", 2)[2].startswith(expected_os_identifier):
            continue

        filename = line.split('"')[1]
        if not valid_release_file(filename):
            continue

        download_url = f"{major_minor_blender_release_url}{filename}"
        break

    if download_url is None:
        raise BlenderVersionNotFound()

    return download_url


def get_nightly_release_download_url(
    blender_version, operative_system, arch, use_cache=True
):
    """Retrieves the download URL for a specific nightly release of Blender.

    Parameters
    ----------

    blender_version : str
      Version for which the URL will be discovered. Should be a valid version
      of Blender, otherwise shows an error an the script will exit with 1 code.

    operative_system : str
      Operative system correspondent to the release.

    bits : str
      Number of bits of the system for the release.

    arch : str
      Identifier of the architecture for which the release will be retrieved.

    use_cache : bool
      Use cache requesting Blender repositories.
    """
    url = "https://builder.blender.org/download/daily/archive/"
    res = GET(url, use_cache=use_cache)
    urls = re.findall(rf'"({url}[^"]+)"', res)

    expected_os_identifier = (
        "darwin" if operative_system == "macos" else operative_system
    )
    expected_extension = {
        "linux": "tar.xz",
        "windows": "zip",
        "macos": "dmg",
    }[operative_system]

    download_url = None

    for url in urls:
        if expected_os_identifier not in url:
            continue
        if f"/blender-{blender_version}-" not in url:
            continue

        arch_ext_split = url.split(f"{expected_os_identifier}.")[1].split("-")
        version_ext = ".".join(arch_ext_split[-1].split(".")[1:])
        if version_ext != expected_extension:
            continue

        version_arch = arch_ext_split[0]
        if arch is not None and arch != version_arch:
            continue

        download_url = url
        break

    if download_url is None:
        raise BlenderVersionNotFound()

    return download_url


def download_release(download_url, output_directory, quiet=False):
    """Downloads the release file from Blender official repository.

    Parameters
    ----------

    download_url : str
      URL of the file to download.

    output_directory : str
      Path to the directory in which the downloaded file will be stored.
    """
    try:
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

        # create temporal blender-downloader directory if not exists to store
        # extracted files
        if not os.path.isdir(TEMPDIR):
            os.mkdir(TEMPDIR)

        tmp_output_filepath = os.path.join(TEMPDIR, output_filename)

        chunksize = 8192
        downloaded_size = chunksize
        res = urlopen(Request(download_url))
        total_size_bytes = int(res.info()["Content-Length"])

        _verify_disk_space(output_directory, total_size_bytes)

        progress_bar_kwargs = dict(
            total=total_size_bytes,
            unit="B",
            desc=f"Downloading '{output_filename}'",
            unit_scale=True,
            unit_divisor=1000,
            miniters=1,
            disable=quiet,
            initial=chunksize,  # first chunk is written before entering while
        )
        with tqdm(**progress_bar_kwargs) as progress_bar, open(
            tmp_output_filepath, "wb"
        ) as f:
            data = res.read(chunksize)
            f.write(data)
            while data:
                data = res.read(chunksize)
                f.write(data)
                progress_bar.update(chunksize)
                downloaded_size += chunksize
                if downloaded_size >= total_size_bytes:
                    break
    except KeyboardInterrupt:
        sys.stderr.write("Download interrupted\n")
        if os.path.isfile(tmp_output_filepath):
            os.remove(tmp_output_filepath)
        sys.exit(1)

    # move from temporal directory to the real output path
    #
    # use `shutil.move` instead of `os.rename` to be able to
    # move files between different hard drives, see:
    # https://stackoverflow.com/a/21116654/9167585
    shutil.move(tmp_output_filepath, output_filepath)

    return output_filepath


def _verify_disk_space(output_dir, total_size):
    free_space = shutil.disk_usage(output_dir).free
    if free_space < total_size:
        sys.stderr.write(
            f"Not enough free space at {output_dir}."
            f" Free space: {free_space} bytes."
            f" Needed: {total_size} bytes."
        )
        sys.exit(1)


def extract_release(zipped_filepath, quiet=False):
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
    try:
        zipped_filename = os.path.basename(zipped_filepath)
        output_directory = os.path.abspath(os.path.dirname(zipped_filepath))
        short_extension = os.path.splitext(zipped_filepath)[-1]

        # filepath of the extracted directory, don't confuse it with
        # `output_directory`, that is the directory where the file to extract
        # is located
        extracted_directory_path = None

        if short_extension == ".zip":
            if not quiet:
                sys.stderr.write(f"Decompressing '{zipped_filename}'...\n")

            with zipfile.ZipFile(zipped_filepath, "r") as f:
                namelist = f.namelist()
                namelist_length = len(namelist)

                # ensure that Blender is extracted in a top level directory
                #
                # MacOS versions previous to 2.79 are released in a ZIP file
                # with multiple directories and files in the root, which results
                # in a messy extraction with a lot of files in the current
                # working directory
                root_dirnames = get_toplevel_dirnames_from_paths(namelist)

                # `not root_dirnames` when only files are found in the ZIP
                if len(root_dirnames) > 1 or not root_dirnames:
                    output_directory = os.path.join(output_directory, "Blender")

                    # don't overwrite existing non empty directory extracting
                    if os.path.isdir(output_directory) and os.listdir(output_directory):
                        sys.stderr.write(
                            f"The directory '{output_directory}' where the files will"
                            " be extracted already exists and is not empty. Extraction"
                            " skipped.\n"
                        )
                        sys.exit(1)

                    extracted_directory_path = output_directory
                else:
                    extracted_directory_path = os.path.join(
                        output_directory, removesuffix(zipped_filename, ".zip")
                    )

                progress_bar_kwargs = dict(
                    total=namelist_length,
                    desc=f"Extracting '{zipped_filename}'",
                    iterable=namelist,
                    disable=quiet,
                )
                for file in tqdm(**progress_bar_kwargs):
                    f.extract(member=file, path=output_directory)

        elif short_extension in [".bz2", ".gz", ".xz"]:
            if not quiet:
                sys.stderr.write(f"Decompressing '{zipped_filename}'...\n")

            with tarfile.open(zipped_filepath, "r") as f:
                files = f.getmembers()
                files_length = len(files)
                paths = [file.name for file in files]

                root_dirnames = get_toplevel_dirnames_from_paths(paths)

                if len(root_dirnames) > 1 or not root_dirnames:
                    output_directory = os.path.join(output_directory, "Blender")
                    extracted_directory_path = output_directory
                else:
                    long_extension = controlled_full_splitext(
                        zipped_filename,
                        [".tar.gz", ".tar.xz", ".tar.bz2", ".gz", ".xz", ".bz2"],
                    )
                    extracted_directory_path = os.path.join(
                        output_directory, removesuffix(zipped_filename, long_extension)
                    )

                progress_bar_kwargs = dict(
                    total=files_length,
                    desc=f"Extracting '{zipped_filename}'",
                    iterable=files,
                    disable=quiet,
                )
                for file in tqdm(**progress_bar_kwargs):
                    f.extract(member=file, path=output_directory)

        elif short_extension == ".dmg":
            running_os = get_running_os()
            if running_os != "macos":
                # we are not in MacOS, so we need the binaries dmg2img and 7z
                # to decompress the `.dmg` file downloaded
                dmg2img, sevenz = shutil.which("dmg2img"), shutil.which("7z")
                if dmg2img is None or sevenz is None:
                    required_programs = []
                    if dmg2img is None:
                        required_programs.append("'dmg2img'")
                    if sevenz is None:
                        required_programs.append("'7z'")
                    plural_suffix = "s" if len(required_programs) > 1 else ""
                    sys.stderr.write(
                        f"You need to install the program{plural_suffix}"
                        f" {' and '.join(required_programs)} to extract the"
                        f" DMG Blender release located at {zipped_filepath}"
                        f" inside a {running_os.capitalize()} platform.\n"
                    )
                    sys.exit(1)

                img_filepath = removesuffix(zipped_filepath, "dmg") + "img"
                if os.path.isfile(img_filepath):
                    os.remove(img_filepath)

                dmg2img_proc = subprocess.Popen(
                    ["dmg2img", zipped_filepath],
                    stderr=sys.stderr,
                    stdout=sys.stdout,
                    env=os.environ,
                )
                dmg2img_proc.communicate()
                if dmg2img_proc.returncode != 0:
                    sys.exit(dmg2img_proc.returncode)

                seven7_proc = subprocess.Popen(
                    ["7z", "x", img_filepath],
                    stderr=sys.stderr,
                    stdout=sys.stdout,
                    env=os.environ,
                )
                seven7_proc.communicate()
                if seven7_proc.returncode != 0:
                    sys.exit(seven7_proc.returncode)

                extracted_directory_path = os.path.join(output_directory, "Blender")
            else:
                # we are inside MacOS, use the DMG CLI utility included in
                # the system through the dmglib Python wrapper
                extracted_directory_path = os.path.join(
                    output_directory,
                    removesuffix(os.path.basename(zipped_filepath), ".dmg"),
                )

                import dmglib

                with dmglib.attachedDiskImage(zipped_filepath) as mounted_dmg:
                    contents_parent_dirpath = None
                    for dirpath, _, _ in os.walk(mounted_dmg[0]):
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
                        extracted_directory_path,
                    )
        else:
            if "-e" in sys.argv and "--extract" not in sys.argv:
                extract_option = "-e"
            elif "-e" not in sys.argv and "--extract" in sys.argv:
                extract_option = "--extract"
            else:
                extract_option = "-e/--extract"
            sys.stderr.write(
                f"File extension '{short_extension}' extraction not"
                " supported by blender-downloader's command line option"
                f" '{extract_option}'.\n"
            )
            sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("Extraction interrupted\n")
        # remove the directory being created, if exists
        if os.path.isdir(extracted_directory_path):
            shutil.rmtree(extracted_directory_path)
        sys.exit(1)

    return extracted_directory_path


def print_executables(
    extracted_directory_path,
    operative_system,
    print_blender_executable,
    print_python_executable,
):
    """Calling this function, the filepaths of the Blender executable and the
    Python interpreter included in Blender will be printed to the standard
    output.

    Parameters
    ----------

    extracted_directory_path : bool
      Blender release directory.

    operative_system : str
      Operative system correspondent to the release.

    print_blender_executable : bool
      Print Blender executable location to the standard output.

    print_python_executable : bool
      Print Python interpreter executable included with Blender to the standard
      output.
    """
    # search executables by operative system
    if operative_system == "linux":
        blender_executable_filepath = os.path.join(
            extracted_directory_path,
            "blender",
        )

        python_executable_filepath = None
        for dirpath, dirnames, files in os.walk(extracted_directory_path):
            if os.path.basename(dirpath) == "bin":
                for filename in files:
                    if filename.startswith("python"):
                        python_executable_filepath = os.path.join(
                            dirpath,
                            filename,
                        )
                        break
                break
    elif operative_system == "windows":
        blender_executable_filepath = os.path.join(
            extracted_directory_path,
            "blender.exe",
        )

        python_executable_filepath = None
        for dirpath, dirnames, files in os.walk(extracted_directory_path):
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
        for dirpath, dirnames, files in os.walk(extracted_directory_path):
            dirname = os.path.basename(dirpath)
            if dirname == "bin":
                for filename in files:
                    if filename.startswith("python"):
                        python_executable_filepath = os.path.join(
                            dirpath,
                            filename,
                        )
                        break
                if blender_executable_filepath:
                    break
            elif dirname == "MacOS" and files[0] in ["Blender", "blender"]:
                blender_executable_filepath = os.path.join(
                    dirpath,
                    files[0],
                )
                if python_executable_filepath:
                    break

    # print executables
    error = False
    if print_blender_executable:
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

    if print_python_executable:
        if python_executable_filepath is None or not os.path.isfile(
            python_executable_filepath
        ):
            sys.stderr.write(
                "Builtin Blender Python interpreter executable filepath not found\n"
            )
            error = True
        else:
            sys.stdout.write(f"{python_executable_filepath}\n")

    if error:
        sys.exit(1)


def list_available_blender_versions(
    maximum_versions, operative_system, bits, arch, use_cache=True
):
    """Prints to stdout all Blender versions available in official repositories.

    The printing order is from greater versions to lower. You can specify a maximum
    number of versions to print using the ``maximum_versions`` parameter.

    Parameters
    ----------

    maximum_versions : int
      Maximum number of versions to print.

    operative_system : str
      Operative system of the releases to be printed. Can be either "linux",
      "macos" or "windows".

    bits : int
      Number of bits of the system. Can be either 64 or 32.

    use_cache : bool
      Use cache requesting Blender repositories.
    """
    n_versions, versions_found = (0, [])

    # Nightly version number
    nightly_version = discover_version_number_by_identifier(
        "nightly",
        use_cache=use_cache,
    )
    sys.stdout.write(f"{nightly_version} (latest)\n")
    versions_found.append(nightly_version)
    n_versions += 1
    if maximum_versions < 2:
        return 0

    # Stable version number
    stable_version = discover_version_number_by_identifier(
        "stable",
        use_cache=use_cache,
    )
    versions_found.append(stable_version)
    if maximum_versions < 3:
        sys.stdout.write(f"{stable_version} (stable)\n")
        return 0
    stable_Version = BlenderVersion(stable_version)
    _stable_version_printed = False

    url = "https://download.blender.org/release/"
    response_lines = GET(url, use_cache=use_cache).splitlines()
    version_matcher = re.compile(r"^\d+\.\d+$")
    min_blender_Version_supported = BlenderVersion(MINIMUM_VERSION_SUPPPORTED)

    for line in reversed(response_lines):
        quote_split = line.split('"')
        if len(quote_split) < 2:
            continue

        blender_split = quote_split[1].split("Blender")
        if len(blender_split) < 2:
            continue

        blender_version = blender_split[1].rstrip("/")
        if not re.match(version_matcher, blender_version):
            continue

        major_minor_blender_Version = BlenderVersion(blender_version)
        if major_minor_blender_Version < min_blender_Version_supported:
            continue

        expected_os_identifier = _build_download_repo_expected_os_identifier(
            operative_system,
            major_minor_blender_Version,
        )

        # build release filename validation function
        valid_release_file = _build_download_repo_release_file_validator(
            operative_system,
            bits,
            arch,
            major_minor_blender_Version,
        )

        major_minor_blender_release_url = f"{url}Blender{blender_version}/"

        repo_response = GET(
            major_minor_blender_release_url,
            use_cache=use_cache,
        ).splitlines()

        repo_versions = []
        for repo_line in reversed(repo_response):
            if not repo_line.startswith(f'<a href="blender-{blender_version}'):
                continue

            if not repo_line.split("-", 2)[2].startswith(expected_os_identifier):
                continue

            filename = repo_line.split('"')[1]
            if not valid_release_file(filename):
                continue

            repo_versions.append(repo_line.split("-")[1])

        # sort versions in reversed order
        repo_versions.sort(key=lambda v: BlenderVersion(v), reverse=True)

        for version in repo_versions:
            # found version
            if version.count(".") > 2:
                version = ".".join(version.split(".")[:3])
            if version in versions_found:
                continue

            # print version
            #   print stable version in their correct place
            if not _stable_version_printed and BlenderVersion(version) < stable_Version:
                sys.stdout.write(f"{stable_version} (stable)\n")
                _stable_version_printed = True
            else:
                sys.stdout.write(f"{version}\n")

            versions_found.append(version)
            n_versions += 1

            if n_versions >= maximum_versions:
                break

        if n_versions >= maximum_versions:
            break

    return 0


def run(args=[]):
    opts = parse_args(args)

    # cache invalidation
    if opts.clear_cache:
        try:
            CACHE.clear()
        except CacheTimeout:
            sys.stderr.write(
                "An error happen clearing blender-downloader's cache.\n"
                f"Please, submit a report to {SCRIPT_NEW_ISSUE_URL} if the"
                " problem persists.\n"
            )
            return 1
        else:
            sys.stdout.write("Cache removed successfully!\n")
            return 0

    if opts.list:
        try:
            return list_available_blender_versions(
                opts.list,
                opts.operative_system,
                opts.bits,
                opts.arch,
                use_cache=opts.use_cache,
            )
        except KeyboardInterrupt:
            return 1
    try:
        download_url = get_legacy_release_download_url(
            opts.blender_version,
            opts.operative_system,
            opts.bits,
            opts.arch,
            use_cache=opts.use_cache,
        )
    except BlenderVersionNotFound:
        try:
            download_url = get_nightly_release_download_url(
                opts.blender_version,
                opts.operative_system,
                opts.arch,
                use_cache=opts.use_cache,
            )
        except BlenderVersionNotFound:
            version_not_found_error_message = (
                f"The release '{opts.blender_version}' can't be located in official"
                " Blender repositories.\nMake sure that you are passing a valid"
                f" version.\n\n"
                f"If you think that '{opts.blender_version}' is a valid release and"
                " this is a problem with blender-downloader, please, report it to"
                f" {SCRIPT_NEW_ISSUE_URL}\n"
            )
            sys.stderr.write(version_not_found_error_message)
            return 1
        except KeyboardInterrupt:
            return 1
    except KeyboardInterrupt:
        return 1

    downloaded_release_filepath = None
    try:
        downloaded_release_filepath = download_release(
            download_url,
            opts.output_directory,
            quiet=QUIET,
        )
        if opts.extract:
            extracted_directory_path = extract_release(
                downloaded_release_filepath,
                quiet=QUIET,
            )

            if opts.print_blender_executable or opts.print_python_executable:
                print_executables(
                    extracted_directory_path,
                    opts.operative_system,
                    opts.print_blender_executable,
                    opts.print_python_executable,
                )

            if opts.remove_compressed:
                os.remove(downloaded_release_filepath)
    except KeyboardInterrupt:
        # other keyboard interruption signals are handled inside the
        # functions, which perform the corresponding cleaning in each

        # clean downloaded file if we were not removed it
        if opts.remove_compressed and os.path.isfile(downloaded_release_filepath):
            os.remove(downloaded_release_filepath)

        return 1

    return 0


def main():  # pragma: no cover
    sys.exit(run(args=sys.argv[1:]))


if __name__ == "__main__":
    main()
