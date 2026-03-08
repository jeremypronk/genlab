#!/usr/bin/env python3
"""
Increments a versioned directory (e.g. v042 -> v043), copies all YAML files
from the source directory to the new one, and updates any version number
found in the filenames to match the new version.

The zero-padding width of the input version is preserved in both the new
directory name and any version tokens found inside filenames.
"""

import argparse
import re
import shutil
from pathlib import Path


def parse_version_dir(dir_name: str) -> tuple[str, str, int]:
    """
    Parse a directory name in the format v<number>.

    Returns:
        prefix      - the leading 'v'
        raw_version - the raw digit string, e.g. '042' (preserves width)
        version     - the integer value, e.g. 42
    """
    match = re.fullmatch(r"(v)(\d+)", dir_name)
    if not match:
        raise ValueError(
            f"Directory name '{dir_name}' does not match expected format "
            "'v<number>' (e.g. v42 or v042)"
        )
    prefix, raw_version = match.group(1), match.group(2)
    return prefix, raw_version, int(raw_version)


def format_version(new_version: int, old_raw: str) -> str:
    """
    Format new_version with the same zero-padded width as old_raw.

    If incrementing causes the number to naturally exceed the original width
    (e.g. 999 -> 1000), the wider representation is used rather than truncating.
    """
    return str(new_version).zfill(len(old_raw))


def rename_yaml_file(filename: str, old_raw: str, new_raw: str) -> str:
    """
    Replace occurrences of the old version token in the filename with the new one.
    Matches both v-prefixed (e.g. v042) and bare integer (e.g. 042) occurrences,
    respecting digit boundaries so partial matches are never replaced.
    """
    # Replace v<old> pattern (e.g. v042 -> v043)
    new_name = re.sub(
        rf"(?<![0-9])v{re.escape(old_raw)}(?![0-9])",
        f"v{new_raw}",
        filename,
    )
    # Replace bare integer occurrences (e.g. _042_ or _042.)
    new_name = re.sub(
        rf"(?<![0-9]){re.escape(old_raw)}(?![0-9])",
        new_raw,
        new_name,
    )
    return new_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Increment a versioned directory and migrate its YAML files."
    )
    parser.add_argument(
        "source_dir",
        help="Source directory in the format v<number>, e.g. v42 or v042",
    )
    args = parser.parse_args()

    source_path = Path(args.source_dir)

    # Validate the source directory exists
    if not source_path.exists():
        raise SystemExit(f"Error: Source directory '{source_path}' does not exist.")
    if not source_path.is_dir():
        raise SystemExit(f"Error: '{source_path}' is not a directory.")

    # Parse the version, preserving the raw digit string for width information
    dir_name = source_path.name
    prefix, old_raw, old_version = parse_version_dir(dir_name)
    new_version = old_version + 1
    new_raw = format_version(new_version, old_raw)

    # Build the new directory path (sibling of the source directory)
    new_dir_name = f"{prefix}{new_raw}"
    new_path = source_path.parent / new_dir_name

    if new_path.exists():
        raise SystemExit(f"Error: Target directory '{new_path}' already exists.")

    # Create the new directory
    new_path.mkdir(parents=True)
    print(f"Created directory: {new_path}")

    # Find and copy all YAML files
    yaml_files = list(source_path.glob("*.yaml")) + list(source_path.glob("*.yml"))

    if not yaml_files:
        print("No YAML files found in the source directory.")
        return

    for src_file in yaml_files:
        new_filename = rename_yaml_file(src_file.name, old_raw, new_raw)
        dest_file = new_path / new_filename
        shutil.copy2(src_file, dest_file)
        if new_filename != src_file.name:
            print(f"  Copied & renamed: {src_file.name}  ->  {new_filename}")
        else:
            print(f"  Copied:           {src_file.name}")

    print(f"\nDone. {len(yaml_files)} YAML file(s) copied to '{new_path}'.")


if __name__ == "__main__":
    main()