import pytest

from blender_downloader import (
    BlenderVersionNotFound,
    discover_version_number_by_identifier,
    get_nightly_release_download_url,
)


@pytest.mark.parametrize('operative_system', ('linux', 'macos', 'windows'))
@pytest.mark.parametrize('arch', ('arm64', None))
def test_get_nightly_release_download_url(operative_system, arch):
    blender_version = discover_version_number_by_identifier('nightly')

    def get_url():
        return get_nightly_release_download_url(
            blender_version,
            operative_system,
            arch,
        )

    if arch == 'arm64' and operative_system == 'linux':
        with pytest.raises(BlenderVersionNotFound):
            get_url()
    else:
        url = get_url()
        assert f'/blender-{blender_version}-' in url
        assert url.startswith('https://')
        assert '.' in url
