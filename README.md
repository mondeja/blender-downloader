# blender-downloader

[![PyPI][pypi-version-badge-link]][pypi-link]
[![Python versions][pypi-pyversions-badge-link]][pypi-link]
[![License][license-image]][license-link]
[![Tests][tests-image]][tests-link]
[![Coverage status][coverage-image]][coverage-link]

Multiplatform Python CLI utility that downloads a specific portable release of
Blender by version/os/bits from official Blender repositories. The minimum
supported version is v2.57.

## Install

```bash
pip install blender-downloader
```

## Usage

> Execute `blender-downloader --help` to see all supported arguments.

### Download release by version number

```bash
blender-downloader 2.92
```

### Download current stable release

```bash
blender-downloader stable
```

### Download stable release, extract/mount and print `blender` executable location

```bash
blender-downloader stable --extract --print-blender-executable
```

### List all available versions to download

```bash
blender-downloader --list
```

[pypi-link]: https://pypi.org/project/blender-downloader
[pypi-version-badge-link]: https://img.shields.io/pypi/v/blender-downloader?logo=pypi&logoColor=white
[pypi-pyversions-badge-link]: https://img.shields.io/pypi/pyversions/blender-downloader?logo=python&logoColor=white
[license-image]: https://img.shields.io/pypi/l/blender-downloader?color=light-green&logo=freebsd&logoColor=white
[license-link]: https://github.com/mondeja/blender-downloader/blob/master/LICENSE
[tests-image]: https://img.shields.io/github/actions/workflow/status/mondeja/blender-downloader/ci.yml?logo=github&label=tests&branch=master
[tests-link]: https://github.com/mondeja/blender-downloader/actions?query=workflow%3ACI
[coverage-image]: https://img.shields.io/codecov/c/github/mondeja/blender-downloader?logo=codecov&logoColor=white
[coverage-link]: https://app.codecov.io/gh/mondeja/blender-downloader
