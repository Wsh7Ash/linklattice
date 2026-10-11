"""File discovery and project configuration loading."""

from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field

CONFIG_FILENAME = ".linklattice.json"
DEFAULT_GLOB = "*.md"
KNOWN_KEYS = ("exclude", "allow", "check_external")


class ConfigError(Exception):
    """Raised when the project config file is missing content or malformed."""


@dataclass
class Config:
    """Effective configuration after merging file config with CLI flags."""

    exclude: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)
    check_external: bool = False
    source: str = "defaults"


def load_config(root: str) -> Config:
    """Load ``.linklattice.json`` from ``root`` (if present).

    Unknown keys are ignored; known keys must have the documented types or a
    :class:`ConfigError` is raised (the CLI turns that into exit code 2).
    """
    path = os.path.join(root, CONFIG_FILENAME)
    config = Config()
    if not os.path.isfile(path):
        return config

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {CONFIG_FILENAME}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{CONFIG_FILENAME} must contain a JSON object")

    exclude = data.get("exclude", [])
    allow = data.get("allow", [])
    check_external = data.get("check_external", False)

    for name, value in (("exclude", exclude), ("allow", allow)):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigError(f'{CONFIG_FILENAME}: "{name}" must be a list of strings')
    if not isinstance(check_external, bool):
        raise ConfigError(f'{CONFIG_FILENAME}: "check_external" must be true or false')

    config = Config(
        exclude=list(exclude),
        allow=list(allow),
        check_external=check_external,
        source=CONFIG_FILENAME,
    )
    return config


def _has_glob_chars(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def is_excluded(rel_path: str, patterns: list[str]) -> bool:
    """True when ``rel_path`` (posix style) matches an exclude pattern.

    Patterns containing glob characters are matched with :mod:`fnmatch`
    against the relative path and the file name; anything else is matched as
    a plain substring of the relative path.
    """
    for pattern in patterns:
        if not pattern:
            continue
        if _has_glob_chars(pattern):
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                rel_path.rsplit("/", 1)[-1], pattern
            ):
                return True
        elif pattern in rel_path:
            return True
    return False


def matches_glob(rel_path: str, pattern: str) -> bool:
    """Match ``rel_path`` against a glob.

    A pattern containing ``/`` is matched against the whole relative path;
    otherwise it is matched against the file name.
    """
    name = rel_path.rsplit("/", 1)[-1]
    if _has_glob_chars(pattern) and "/" in pattern:
        return fnmatch.fnmatch(rel_path, pattern)
    return fnmatch.fnmatch(name, pattern)


def discover_files(root: str, pattern: str, excludes: list[str]) -> list[tuple[str, str]]:
    """Recursively discover files under ``root``.

    Returns a sorted list of ``(absolute_path, relative_posix_path)``.  When
    ``root`` is a single file it is returned as-is with its file name as the
    relative path.
    """
    if os.path.isfile(root):
        rel = os.path.basename(root).replace(os.sep, "/")
        if is_excluded(rel, excludes):
            return []
        return [(os.path.abspath(root), rel)]

    found: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if not is_excluded(_rel(root, os.path.join(dirpath, d)), excludes)
        )
        for filename in sorted(filenames):
            rel = _rel(root, os.path.join(dirpath, filename))
            if not matches_glob(rel, pattern):
                continue
            if is_excluded(rel, excludes):
                continue
            found.append((os.path.abspath(os.path.join(dirpath, filename)), rel))
    return sorted(found, key=lambda item: item[1])


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def read_text(path: str) -> str:
    """Read a file as UTF-8, replacing undecodable bytes."""
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()
