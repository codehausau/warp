import os
import re
import subprocess
from pathlib import Path

VERSION = "2.0.3"


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _sanitize_local_version_part(value):
    return re.sub(r'[^0-9A-Za-z]+', '.', value).strip('.')


def _get_git_build_metadata():
    try:
        count = subprocess.check_output(
            ['git', 'rev-list', '--count', 'HEAD'],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""

    parts = []
    if count:
        parts.append(count)
    if sha:
        parts.append(f"g{sha}")

    return ".".join(parts)


def _get_exact_git_tag():
    try:
        return subprocess.check_output(
            ['git', 'describe', '--tags', '--exact-match', 'HEAD'],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def get_version():
    exact_tag = _get_exact_git_tag()
    if exact_tag in {VERSION, f"v{VERSION}"}:
        return VERSION

    parts = []

    git_build = _get_git_build_metadata()
    if git_build:
        parts.append(git_build)

    build = _sanitize_local_version_part(os.environ.get("WARP_BUILD", "").strip())
    if build:
        parts.append(build)

    if parts:
        return f"{VERSION}+{'.'.join(parts)}"

    return VERSION


def get_runtime_version():
    return get_version()


__version__ = get_version()
