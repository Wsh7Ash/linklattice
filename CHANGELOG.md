# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/) loosely,
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-10

### Added

- Recursive Markdown discovery with `--glob` (default `*.md`) and repeatable
  `--exclude` filters (substring or glob).
- Link extraction for inline `[text](target)` / `![alt](target)`, reference
  definitions `[label]: target` and usages `[text][label]`, plus HTML
  `<a href>` / `<img src>`.
- Target classification: external, absolute, in-page anchor, relative file,
  relative file + anchor.
- Validation of relative file existence (with letter-case mismatch detection),
  image paths, and GitHub-style heading anchors (`#slug`, duplicate slugs
  suffixed `-1`, `-2`, explicit HTML `id=` / `name=` anchors).
- Code awareness: fenced blocks (``` and ~~~), YAML front matter and inline
  code spans are never treated as links or headings.
- `--format text|json` reports, `--quiet`, `--no-summary`.
- `.linklattice.json` project config merged with CLI flags (CLI wins).
- `--check-external` opt-in HTTP HEAD/GET verification (zero network I/O by
  default).
- Exit codes: 0 clean, 1 errors found, 2 usage/config error.
- `unittest` suite (93 tests) runnable with the standard library only.
