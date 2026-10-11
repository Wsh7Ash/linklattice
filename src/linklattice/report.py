"""Text and JSON report renderers."""

from __future__ import annotations

import json

from linklattice import __version__
from linklattice.checks import Finding, Result


def summary_line(result: Result) -> str:
    return (
        f"Summary: {result.files_scanned} files scanned, "
        f"{result.links_checked} links checked, "
        f"{result.errors} errors, {result.warnings} warnings, "
        f"{result.skipped} skipped in {result.duration:.2f}s"
    )


def render_text(result: Result, *, show_summary: bool = True) -> str:
    """Render findings grouped by file, optionally followed by a summary line."""
    groups: dict[str, list[Finding]] = {}
    for finding in result.findings:
        groups.setdefault(finding.file, []).append(finding)

    lines: list[str] = []
    for file in sorted(groups):
        lines.append(file)
        for finding in sorted(groups[file], key=lambda f: (f.line, f.target)):
            lines.append(
                f"  {finding.line:>5}  {finding.severity:<7} "
                f"{finding.target}  |  {finding.reason}"
            )
        lines.append("")

    while lines and not lines[-1]:
        lines.pop()

    if show_summary:
        if lines:
            lines.append("")
        lines.append(summary_line(result))
    return "\n".join(lines) + ("\n" if lines else "")


def render_json(result: Result, *, include_summary: bool = True) -> str:
    """Render a stable, machine-parseable JSON report.

    The output is always a single JSON document - never followed by extra
    text - so it can be piped straight into a parser.
    """
    summary = {
        "duration_seconds": round(result.duration, 3),
        "errors": result.errors,
        "files_scanned": result.files_scanned,
        "links_checked": result.links_checked,
        "root": result.root,
        "skipped": result.skipped,
        "warnings": result.warnings,
    }
    payload = {
        "findings": [
            {
                "file": finding.file,
                "line": finding.line,
                "reason": finding.reason,
                "severity": finding.severity,
                "target": finding.target,
            }
            for finding in sorted(
                result.findings, key=lambda f: (f.file, f.line, f.target)
            )
        ],
        "tool": {"name": "linklattice", "version": __version__},
    }
    if include_summary:
        payload["summary"] = summary
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
