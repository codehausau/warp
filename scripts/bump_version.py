#!/usr/bin/env python3

import argparse
import pathlib
import re
import sys


VERSION_FILE = pathlib.Path(__file__).resolve().parents[1] / "warp" / "version.py"
VERSION_RE = re.compile(r'^(VERSION = ")(\d+)\.(\d+)\.(\d+)(")$', re.MULTILINE)


def bump_version_text(text, part="patch"):
    match = VERSION_RE.search(text)
    if match is None:
        raise ValueError("VERSION assignment not found")

    major, minor, patch = [int(i) for i in match.groups()[1:4]]

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown bump part: {part}")

    new_version = f"{major}.{minor}.{patch}"
    new_text = VERSION_RE.sub(rf'\g<1>{new_version}\g<5>', text, count=1)
    return new_text, new_version


def bump_version_file(path=VERSION_FILE, part="patch"):
    text = path.read_text(encoding="utf8")
    new_text, new_version = bump_version_text(text, part=part)
    path.write_text(new_text, encoding="utf8")
    return new_version


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", nargs="?", choices=["major", "minor", "patch"], default="patch")
    args = parser.parse_args(argv)

    new_version = bump_version_file(part=args.part)
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
