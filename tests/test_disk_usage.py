import pytest

from blender_downloader.disk_utils import _get_free_space_at, _has_enough_disk_space_at_directory

def test_get_free_space_is_the_same_at_same_driver():
   assert _get_free_space_at("../") == _get_free_space_at("/")

def test_check_has_enough_space():
   assert _has_enough_disk_space_at_directory("/", 0) 

   assert _has_enough_disk_space_at_directory("/", 2**9999) == False

def test_check_has_enough_negative_space_raises_exception():
   with pytest.raises(Exception):
      _has_enough_disk_space_at_directory("/", -1)

def test_get_free_space_handles_invalid_paths():
   with pytest.raises(FileNotFoundError):
      _get_free_space_at(".23r-2kf0-3k32-g0\\/invalid_path")