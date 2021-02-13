# blender-downloader

Multiplatorm Python CLI utility that just downloads a specific portable
release of Blender by version/os/bits from official Blender repositories. The
minimum supported version is v2.64.

## Install

```bash
pip install blender-downloader
```

## Usage

Execute `blender-downloader --help` to see all supported arguments.

### Download release by version number

```bash
blender-downloader 2.90
```

### Download current stable release

```bash
blender-downloader stable
```

### Download nightly release and extract/mount it, showing executable paths

```bash
blender-downloader nightly --extract --print-executables
```
