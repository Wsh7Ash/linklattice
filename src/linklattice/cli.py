"""Command line interface.

Exit codes:

* ``0`` - no errors found (warnings may still be present)
* ``1`` - at least one error finding
* ``2`` - usage or configuration error
"""

from __future__ import annotations

import argparse
import os
import sys

from linklattice import __version__
from linklattice.checks import scan
from linklattice.report import render_json, render_text, summary_line
from linklattice.scanner import DEFAULT_GLOB, Config, ConfigError, load_config

USAGE_EXIT = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linklattice",
        description=(
            "Offline Markdown reference integrity checker: broken relative "
            "links, broken image paths and broken heading anchors."
        ),
    )
    parser.add_argument("path", nargs="?", help="directory (or single file) to scan")
    parser.add_argument(
        "--glob",
        default=None,
        metavar="PATTERN",
        help=f"file name glob to scan (default: {DEFAULT_GLOB})",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip paths matching this substring or glob (repeatable)",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="PATTERN",
        help="suppress findings for targets matching this substring or glob (repeatable)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default=None,
        dest="output_format",
        help="report format (default: text)",
    )
    parser.add_argument(
        "--check-external",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="verify http(s) links over the network (off by default; no network I/O otherwise)",
    )
    parser.add_argument("--quiet", action="store_true", help="print only the summary line")
    parser.add_argument("--no-summary", action="store_true", help="omit the summary line")
    parser.add_argument(
        "--version", action="version", version=f"linklattice {__version__}"
    )
    return parser


def _merge(args: argparse.Namespace, config: Config) -> Config:
    return Config(
        exclude=list(config.exclude) + list(args.exclude),
        allow=list(config.allow) + list(args.allow),
        check_external=(
            config.check_external
            if args.check_external is None
            else bool(args.check_external)
        ),
        source=config.source,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.path:
        print("linklattice: error: a path to scan is required", file=sys.stderr)
        return USAGE_EXIT

    root = args.path
    if not os.path.exists(root):
        print(f"linklattice: error: path does not exist: {root}", file=sys.stderr)
        return USAGE_EXIT
    if not (os.path.isdir(root) or os.path.isfile(root)):
        print(f"linklattice: error: not a directory or file: {root}", file=sys.stderr)
        return USAGE_EXIT

    scan_root = root if os.path.isdir(root) else os.path.dirname(os.path.abspath(root)) or "."
    try:
        config = load_config(scan_root)
    except ConfigError as exc:
        print(f"linklattice: error: {exc}", file=sys.stderr)
        return USAGE_EXIT

    config = _merge(args, config)
    pattern = args.glob or DEFAULT_GLOB
    output_format = args.output_format or "text"

    try:
        result = scan(root, pattern=pattern, config=config)
    except (ConfigError, OSError) as exc:
        print(f"linklattice: error: {exc}", file=sys.stderr)
        return USAGE_EXIT

    show_summary = not args.no_summary
    if output_format == "json":
        sys.stdout.write(render_json(result, include_summary=show_summary))
        return 1 if result.errors else 0

    if args.quiet:
        if show_summary:
            print(summary_line(result))
    else:
        sys.stdout.write(render_text(result, show_summary=show_summary))

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
