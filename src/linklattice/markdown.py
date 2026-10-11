"""Markdown link extraction.

Extracts inline links/images, reference definitions and usages, and plain
HTML ``<a href>`` / ``<img src>`` attributes.  Link-looking syntax inside
fenced code blocks (``` and ~~~), YAML front matter and inline code spans
is ignored.  Every link carries the 1-based line number it was found on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
INLINE_LINK_RE = re.compile(
    r"(?P<img>!)?\[(?P<text>[^\[\]]*)\]\(\s*"
    r"(?:<(?P<angle>[^<>]*)>|(?P<bare>[^()\s]+))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
REF_DEF_RE = re.compile(r"^ {0,3}\[(?P<label>[^\[\]]+)\]:\s*(?P<target><[^>]*>|\S+)")
REF_USE_RE = re.compile(r"\[(?P<text>[^\[\]]*)\]\[(?P<label>[^\[\]]*)\]")
HTML_A_RE = re.compile(
    r"<a\b[^>]*?\bhref\s*=\s*(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)')", re.IGNORECASE
)
HTML_IMG_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)')", re.IGNORECASE
)
CODE_SPAN_DOUBLE_RE = re.compile(r"``.*?``")
CODE_SPAN_SINGLE_RE = re.compile(r"`[^`\n]*`")


@dataclass(frozen=True)
class Link:
    """A single link reference found in a Markdown file."""

    line: int
    target: str
    kind: str  # inline | reference_def | reference_use | html
    is_image: bool = False


@dataclass
class Extraction:
    """Links plus the reference-label table for the file they came from."""

    links: list[Link] = field(default_factory=list)
    definitions: dict[str, str] = field(default_factory=dict)


def normalize_label(label: str) -> str:
    """Normalize a reference label the way CommonMark does (folded, lowercased)."""
    return re.sub(r"\s+", " ", label).strip().lower()


def strip_code_spans(line: str) -> str:
    """Blank out inline code spans, preserving column positions."""
    line = CODE_SPAN_DOUBLE_RE.sub(lambda m: " " * len(m.group(0)), line)
    line = CODE_SPAN_SINGLE_RE.sub(lambda m: " " * len(m.group(0)), line)
    return line


def strip_code_span_markers(line: str) -> str:
    """Remove backtick markers but keep the code span content (for slug text)."""
    return line.replace("`", "")


def _is_fence_start(line: str) -> tuple[str, int] | None:
    m = FENCE_RE.match(line)
    if not m:
        return None
    fence = m.group("fence")
    info = m.group("info")
    if fence[0] == "`" and "`" in info:
        return None
    return fence[0], len(fence)


def _is_fence_end(line: str, char: str, length: int) -> bool:
    m = FENCE_RE.match(line)
    if not m:
        return False
    fence = m.group("fence")
    if fence[0] != char or len(fence) < length:
        return False
    return m.group("info").strip() == ""


def mask_fenced(text: str) -> str:
    """Return ``text`` with YAML front matter and fenced code blocks blanked.

    Line numbers are preserved: one blank line replaces every masked line.
    """
    lines = text.splitlines()
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0

    if lines and lines[0].strip() == "---":
        out.append("")
        closed = False
        for line in lines[1:]:
            if line.strip() in ("---", "..."):
                closed = True
                out.append("")
                break
            out.append("")
        rest = lines[len(out):]
        if not closed:
            rest = []
        lines = rest

    for line in lines:
        if fence_char is None:
            start = _is_fence_start(line)
            if start:
                fence_char, fence_len = start
                out.append("")
                continue
            out.append(line)
        else:
            out.append("")
            if _is_fence_end(line, fence_char, fence_len):
                fence_char = None
    return "\n".join(out)


def extract_links(text: str) -> Extraction:
    """Extract every link reference from ``text``.

    Returns the links (sorted by line, then by column) and the reference
    label table defined in the same file.
    """
    masked = mask_fenced(text)
    extraction = Extraction()

    for lineno, raw in enumerate(masked.splitlines(), 1):
        line = strip_code_spans(raw)
        candidates: list[tuple[int, int, str, str, bool]] = []

        for m in INLINE_LINK_RE.finditer(line):
            target = m.group("angle")
            if target is None:
                target = m.group("bare") or ""
            candidates.append((m.start(), m.end(), "inline", target, bool(m.group("img"))))

        m = REF_DEF_RE.match(line)
        if m:
            target = m.group("target")
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            elif (
                len(target) >= 2
                and target[0] == target[-1]
                and target[0] in ("'", '"')
            ):
                target = target[1:-1]
            label = normalize_label(m.group("label"))
            extraction.definitions[label] = target
            candidates.append((m.start(), m.end(), "reference_def", target, False))

        for m in REF_USE_RE.finditer(line):
            label = m.group("label") or m.group("text")
            candidates.append((m.start(), m.end(), "reference_use", label, False))

        for m in HTML_A_RE.finditer(line):
            target = m.group("dq") if m.group("dq") is not None else m.group("sq") or ""
            candidates.append((m.start(), m.end(), "html", target, False))

        for m in HTML_IMG_RE.finditer(line):
            target = m.group("dq") if m.group("dq") is not None else m.group("sq") or ""
            candidates.append((m.start(), m.end(), "html", target, True))

        candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        last_end = -1
        for start, end, kind, target, is_image in candidates:
            if start < last_end:
                continue
            last_end = end
            extraction.links.append(Link(line=lineno, target=target, kind=kind, is_image=is_image))

    return extraction
