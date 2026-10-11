"""Validation logic: classify each link target and check it.

Severity model:

* ``error``   - a broken local target (missing file, missing/mismatched case,
  missing heading anchor).
* ``warning`` - skipped or ambiguous cases (an anchor on a non-Markdown file,
  an empty target, an unreachable external link when ``--check-external`` is
  on).

External ``http``/``https``/``mailto`` links are skipped by default and the
default run performs **zero** network I/O.  The network path only exists
behind :func:`http_status`, which is called exclusively when
``check_external`` is enabled.
"""

from __future__ import annotations

import fnmatch
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from linklattice.anchors import collect_anchors
from linklattice.markdown import Extraction, Link, extract_links, normalize_label
from linklattice.scanner import Config, discover_files, read_text

SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown", ".mkd", ".mdx")
USER_AGENT = "linklattice link checker (+offline by default)"


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    target: str
    reason: str
    severity: str  # error | warning


@dataclass
class Result:
    root: str
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    links_checked: int = 0
    skipped: int = 0
    duration: float = 0.0

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def ok(self) -> bool:
        return self.errors == 0


def http_status(url: str, timeout: float = 10.0) -> int | None:
    """Return the HTTP status for ``url``, or ``None`` if it could not be reached.

    Only ever called when ``--check-external`` is enabled.  Tries HEAD first
    and falls back to GET for servers that reject HEAD.
    """
    headers = {"User-Agent": USER_AGENT}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return int(response.status)
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (400, 403, 405, 501):
                continue
            return int(exc.code)
        except (urllib.error.URLError, OSError, ValueError):
            return None
    return None


def _is_allowed(target: str, rel_path: str, allows: list[str]) -> bool:
    for pattern in allows:
        if not pattern:
            continue
        if any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
        elif target == pattern or target.startswith(pattern) or pattern in rel_path:
            return True
    return False


def _case_mismatch(path: str) -> bool:
    """True when ``path`` exists only with different letter casing."""
    absolute = os.path.abspath(path)
    drive, rest = os.path.splitdrive(absolute)
    current = drive + os.sep
    parts = [p for p in rest.split(os.sep) if p]
    for part in parts:
        try:
            entries = os.listdir(current)
        except OSError:
            return False
        if part in entries:
            current = os.path.join(current, part)
            continue
        lowered = {entry.lower() for entry in entries}
        return part.lower() in lowered
    return False


def _split_target(target: str) -> tuple[str, str]:
    base, _, fragment = target.partition("#")
    return base, fragment


def _looks_markdown(path: str) -> bool:
    return path.lower().endswith(MARKDOWN_SUFFIXES)


class _Validator:
    def __init__(self, root: str, config: Config, allows: list[str]):
        self.root = root
        self.config = config
        self.allows = allows
        self.result = Result(root=root)
        self._anchor_cache: dict[str, set[str]] = {}
        self._reported_references: set[tuple[str, str]] = set()

    def anchors_for(self, path: str) -> set[str]:
        if path not in self._anchor_cache:
            try:
                self._anchor_cache[path] = collect_anchors(read_text(path))
            except OSError:
                self._anchor_cache[path] = set()
        return self._anchor_cache[path]

    def add(self, finding: Finding) -> None:
        self.result.findings.append(finding)

    def check_file(self, path: str, rel: str) -> None:
        try:
            text = read_text(path)
        except OSError as exc:
            self.add(Finding(rel, 0, rel, f"cannot read file: {exc}", "error"))
            return

        self.result.files_scanned += 1
        extraction = extract_links(text)
        own_anchors = collect_anchors(text)
        directory = os.path.dirname(os.path.abspath(path))

        for link in self._ordered(extraction):
            target = self._resolve(link, extraction)
            if target is None:
                continue
            self.result.links_checked += 1
            if _is_allowed(target, rel, self.allows):
                self.result.skipped += 1
                continue
            self._check_target(rel, link, target, directory, own_anchors)

    @staticmethod
    def _ordered(extraction: Extraction) -> list[Link]:
        return sorted(extraction.links, key=lambda link: link.line)

    def _resolve(self, link: Link, extraction: Extraction) -> str | None:
        if link.kind != "reference_use":
            return link.target
        resolved = extraction.definitions.get(normalize_label(link.target))
        if resolved is None:
            return None  # CommonMark treats an undefined reference as plain text
        return resolved

    def _check_target(
        self,
        rel: str,
        link: Link,
        target: str,
        directory: str,
        own_anchors: set[str],
    ) -> None:
        if target == "":
            self._report(rel, link, target, "empty link target", "warning")
            return

        if SCHEME_RE.match(target) or target.startswith("//"):
            self._check_external(rel, link, target)
            return

        base, fragment = _split_target(target)
        if not base:
            if fragment:
                self._check_anchor(rel, link, f"#{fragment}", own_anchors, fragment)
            return

        path = urllib.parse.unquote(base)
        if path.startswith("/"):
            resolved = os.path.normpath(path)
        else:
            resolved = os.path.normpath(os.path.join(directory, path))
        self._check_exists(rel, link, target, path, resolved, fragment)

    def _check_exists(
        self, rel: str, link: Link, raw_target: str, path: str, resolved: str, fragment: str
    ) -> None:
        if not os.path.exists(resolved):
            self._report(rel, link, raw_target, f"target does not exist: {path}", "error")
            return
        if _case_mismatch(resolved):
            self._report(
                rel,
                link,
                raw_target,
                f"target path letter-case does not match the file on disk: {path}",
                "error",
            )
            return
        if not fragment:
            return
        if os.path.isdir(resolved):
            self._report(
                rel,
                link,
                raw_target,
                f"anchor '#{fragment}' points at a directory, cannot verify",
                "warning",
            )
            return
        if not _looks_markdown(resolved):
            self._report(
                rel,
                link,
                raw_target,
                f"anchor '#{fragment}' not verified: target is not a Markdown file",
                "warning",
            )
            return
        self._check_anchor(rel, link, raw_target, self.anchors_for(resolved), fragment)

    def _check_anchor(
        self, rel: str, link: Link, raw_target: str, anchors: set[str], fragment: str
    ) -> None:
        if fragment not in anchors:
            self._report(
                rel, link, raw_target, f"anchor #{fragment} does not exist", "error"
            )

    def _check_external(self, rel: str, link: Link, target: str) -> None:
        scheme = target.split(":", 1)[0].lower()
        if scheme not in ("http", "https"):
            self.result.skipped += 1
            return
        if not self.config.check_external:
            self.result.skipped += 1
            return
        status = http_status(target)
        if status is None:
            self._report(rel, link, target, "external link unreachable", "warning")
        elif status >= 400:
            self._report(rel, link, target, f"external link returned HTTP {status}", "warning")

    def _report(self, rel: str, link: Link, target: str, reason: str, severity: str) -> None:
        if link.kind in ("reference_def", "reference_use"):
            key = (rel, target)
            if key in self._reported_references:
                return
            self._reported_references.add(key)
        self.add(Finding(rel, link.line, target, reason, severity))


def scan(
    root: str,
    *,
    pattern: str = "*.md",
    config: Config | None = None,
    excludes: list[str] | None = None,
    allows: list[str] | None = None,
) -> Result:
    """Scan ``root`` and return a :class:`Result`.

    ``excludes`` and ``allows`` are merged on top of ``config`` (CLI flags
    extend the config file lists).  No network I/O happens unless
    ``config.check_external`` is true.
    """
    started = time.perf_counter()
    config = config or Config()
    effective_excludes = list(config.exclude) + list(excludes or [])
    effective_allows = list(config.allow) + list(allows or [])

    validator = _Validator(root, config, effective_allows)
    for path, rel in discover_files(root, pattern, effective_excludes):
        validator.check_file(path, rel)

    validator.result.duration = time.perf_counter() - started
    validator.result.findings.sort(key=lambda f: (f.file, f.line, f.target))
    return validator.result
