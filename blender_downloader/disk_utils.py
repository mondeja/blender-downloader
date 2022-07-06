import sys
import os 
import shutil

def verify_disk_space(output_directory, total_size_bytes):
    sys.stdout.write(f"Verifying if {output_directory} has enough space...\n")
    try:
        if not _has_enough_disk_space_at_directory(output_directory, total_size_bytes):
            sys.stderr.write(
                    f"Free space: {_get_free_space_at(output_directory)} bytes\n"
                    f"Total size: {total_size_bytes} bytes\n"
                    f"Not enough space. Exitting.\n"
                )
            sys.exit(1)
        sys.stdout.write("OK.\n")
        sys.stdout.write(f"Free space: {_get_free_space_at(output_directory)} bytes\n")
        sys.stdout.write(f"Total size: {total_size_bytes} bytes\n")
    except FileNotFoundError as e:
        sys.stderr.write(f"Directory was not found. \n")
        sys.exit(1)

def _has_enough_disk_space_at_directory(output_directory, total_size_bytes):
    if total_size_bytes < 0:
        raise ValueError(f"total_size_bits must be greater than 0. Something went wrong. (got {total_size_bytes}")

    free_space_bytes = _get_free_space_at(output_directory)
    return free_space_bytes > total_size_bytes

def _get_free_space_at(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path '{path}' does not exist.")
    return shutil.disk_usage(path).free