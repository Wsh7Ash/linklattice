# Project Spec - linklattice

## Name

`linklattice`

## Category

CLI tool

## Target user

Docs maintainers, README-heavy repository owners, and static-site authors who
need a fast offline check that the Markdown they ship still resolves.

## Problem

Markdown links rot silently. Files get renamed, headings get reworded, images
move, and reference labels drift. Nothing tells the author until a reader hits
a 404 page or a `#anchor` that scrolls nowhere. Existing checkers either need
network access, a full static-site build, or a pile of dependencies.

## Solution

A single-file-tree scanner that parses Markdown itself (code fences and inline
code excluded), validates every **local** reference - relative files, image
paths and GitHub-style heading anchors - and prints a grouped, line-numbered
report or a stable JSON document. External links are skipped unless explicitly
requested.

## Core workflow

1. `python -m linklattice <path>` scans the path recursively for `*.md`.
2. Extract links: inline `[text](target)` / `![alt](target)`, reference
   definitions `[label]: target` and usages `[text][label]`, HTML
   `<a href>` / `<img src>`.
3. Classify each target: external, absolute path, in-page `#anchor`, relative
   file, relative file + anchor.
4. Validate: file exists (letter-case checked), image exists, anchor resolves
   against the target file's GitHub heading slugs.
5. Report findings grouped by file with line number, raw target, reason and
   severity; print a summary.
6. Exit 0 (no errors), 1 (at least one error), 2 (usage/config error).

## Must-have features

- Recursive scan with `--glob` (default `*.md`) and repeatable `--exclude`.
- `--format text|json`; JSON is machine-parseable and structurally stable.
- `--check-external` performs HTTP HEAD/GET **only** when passed; default run
  performs zero network I/O.
- `.linklattice.json` at the scan root with `exclude`, `allow`,
  `check_external`, merged with CLI flags (CLI wins).
- `--quiet` (summary only) and `--no-summary`.
- Summary: files scanned, links checked, errors, warnings, skipped, duration.
- Ignore link-looking syntax inside fenced code blocks (``` / ~~~), YAML front
  matter and inline code spans.
- Severity model: error = broken local target/anchor, warning =
  skipped/ambiguous.

## Nice-to-have features

- Letter-case mismatch detection on case-insensitive file systems.
- Reference-label deduplication so a broken definition is reported once.
- Setext heading support alongside ATX headings.
- Single-file mode (`linklattice README.md`).

## Stack

- Python 3.14 (developed), syntax targets 3.10+.
- Standard library only: `argparse`, `re`, `os`, `json`, `fnmatch`,
  `urllib.request`, `unittest`.
- No pip installs, no network access for validation.
- Tests: `python -m unittest discover -s tests -v`.

## Test strategy

`unittest` with `tempfile.TemporaryDirectory` fixtures. Coverage targets:

- valid relative link resolves; broken file link reported as an error with the
  correct line number
- broken `#missing-heading` reported, valid anchor passes
- heading slug edge cases: punctuation, uppercase, duplicate headings getting
  `-1` suffixes, non-ASCII headings
- links inside fenced code blocks and inline code spans are ignored
- external `http` links are skipped by default with no network attempted and
  counted as skipped
- reference-style definitions resolve; undefined references are not falsely
  flagged
- JSON output parses and contains the expected keys; exit codes 0 / 1 / 2
- config `exclude` and `allow` take effect (file config and CLI flags)

The only network-touching test is skipped unless `LINKLATTICE_NET_TESTS=1`.

## Demo / result strategy

- `examples/sample-docs/` - a small fixture tree with deliberately broken
  links, a `.linklattice.json` demonstrating `exclude` and `allow`.
- Reports are generated from that tree into `results/sample-report.txt` and
  `results/sample-report.json` and committed.
- `RESULTS.md` records only commands that were actually executed and their
  observed output.

## Safety considerations

- Default run performs no socket I/O of any kind; the HTTP client is only
  reachable through `--check-external`.
- No file is ever modified - the tool only reads.
- Files are read as UTF-8 with replacement characters, so a binary file
  mislabelled `.md` cannot crash the scan.
- Reports never include absolute paths unless the caller passes one.
- `--check-external` sends a HEAD (falling back to GET) with a clearly named
  User-Agent; it is opt-in so scans of private docs stay private.

## Definition of done

- `python -m unittest discover -s tests -v` passes with zero failures.
- Demo run against `examples/sample-docs/` produces the committed reports and
  exits 1.
- README, spec, architecture and usage docs match observed behaviour.
- No placeholder code, no third-party dependencies, no network in the default
  path.

## See also

- [Architecture](ARCHITECTURE.md)
- [Usage](USAGE.md)
- [Severity model](ARCHITECTURE.md#severity-model)
- [Project README](../README.md)

