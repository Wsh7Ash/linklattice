"""Heading slugs and anchor collection using GitHub's slug algorithm.

Algorithm (as specified for this project):

* lowercase
* strip punctuation except hyphens and underscores (unicode letters kept)
* spaces become hyphens
* repeated slugs are de-duplicated with ``-1``, ``-2``, ... suffixes
* explicit HTML ``id=`` / ``name=`` attributes are accepted as anchors too

ATX headings (``# ...``), Setext headings (``text`` over ``===``/``---``) and
explicit HTML anchors are collected; fenced code blocks and YAML front matter
are ignored.
"""

from __future__ import annotations

import re

from linklattice.markdown import mask_fenced, strip_code_span_markers

ATX_RE = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?P<space>\s+)(?P<text>.*?)\s*$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-{2,})\s*$")
HTML_ANCHOR_RE = re.compile(r"\b(?:id|name)\s*=\s*(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)')", re.IGNORECASE)


def slugify(text: str) -> str:
    """Convert heading text to a GitHub-style anchor slug."""
    t = text.strip()
    t = strip_code_span_markers(t)
    t = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"\1", t)
    t = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"\1", t)
    t = re.sub(r"(?<![\w])\*(?=\S)(.+?)(?<=\S)\*(?![\w])", r"\1", t)
    t = t.strip("_")
    t = t.lower()
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    t = t.replace(" ", "-")
    return t


def _dedupe(slugs: list[str]) -> set[str]:
    counts: dict[str, int] = {}
    result: set[str] = set()
    for slug in slugs:
        if slug in counts:
            counts[slug] += 1
            result.add(f"{slug}-{counts[slug]}")
        else:
            counts[slug] = 0
            result.add(slug)
    return result


def collect_anchors(text: str) -> set[str]:
    """Collect every anchor that heading links may target in ``text``."""
    masked = mask_fenced(text)
    lines = [strip_code_span_markers(line) for line in masked.splitlines()]

    slugs: list[str] = []
    explicit: list[str] = []

    for line in lines:
        for am in HTML_ANCHOR_RE.finditer(line):
            value = am.group("dq") if am.group("dq") is not None else am.group("sq")
            if value:
                explicit.append(value)

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        m = ATX_RE.match(line)
        if m and m.group("text"):
            slugs.append(slugify(m.group("text")))
            index += 1
            continue
        if (
            line.strip()
            and index + 1 < len(lines)
            and SETEXT_RE.match(lines[index + 1])
            and lines[index + 1].strip()
        ):
            slugs.append(slugify(line))
            index += 2
            continue
        index += 1

    anchors = _dedupe(slugs)
    anchors.update(explicit)
    return anchors
