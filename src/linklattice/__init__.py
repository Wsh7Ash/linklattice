"""linklattice - offline Markdown reference integrity checker.

Scans a folder of Markdown files for broken relative links, broken image
paths and broken heading anchors, then emits a human-readable or JSON
report.  The default run performs zero network I/O.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
