"""Shared test support: puts ``src/`` on ``sys.path`` and provides fixtures."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def run_cli(*args: str):
    """Run ``linklattice.cli.main`` in-process; returns ``(code, stdout, stderr)``."""
    from linklattice.cli import main

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(args))
        except SystemExit as exc:  # argparse usage errors
            code = exc.code if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


class TempTreeTestCase(unittest.TestCase):
    """Base class providing a temporary directory tree of Markdown files."""

    def setUp(self) -> None:
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name

    def write(self, rel: str, content: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        return path

    def scan(self, **kwargs):
        from linklattice.checks import scan

        return scan(self.root, **kwargs)
