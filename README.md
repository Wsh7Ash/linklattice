# linklattice

**An offline Markdown reference integrity checker: it finds broken relative
links, broken image paths and broken heading anchors across a folder of
Markdown files, then emits a human-readable or JSON report.**

## The problem

Markdown links rot silently. Files get renamed, headings get reworded, images
move, reference labels drift - and nothing tells you until a reader hits a 404
or a `#anchor` that scrolls nowhere. Most link checkers want network access,
a full static-site build, or a pile of dependencies. `linklattice` only reads
the files you already have.

## Key features

- Recursive scan with `--glob` (default `*.md`) and repeatable `--exclude`.
- Extracts inline `[text](target)` / `![alt](target)`, reference definitions
  `[label]: target` and usages `[text][label]`, plus HTML `<a href>` and
  `<img src>`.
- Classifies targets: external, absolute path, in-page `#anchor`, relative
  file, relative file + anchor.
- Validates file and image existence (with letter-case mismatch detection) and
  heading anchors using GitHub's slug algorithm - lowercased, punctuation
  stripped, spaces to hyphens, duplicate slugs suffixed `-1`, `-2`, ... and
  explicit HTML `id=` / `name=` attributes accepted.
- Ignores link-looking syntax inside fenced code blocks (``` and ~~~), YAML
  front matter and inline code spans - for links *and* for headings.
- `--format text|json` output; the JSON document has a stable shape.
- `--check-external` performs a plain HTTP HEAD/GET - and **only** then. A
  default run performs zero network I/O.
- `.linklattice.json` project config merged with CLI flags (CLI wins).
- Exit codes: `0` clean, `1` errors found, `2` usage/config error.

## Real terminal example

Running against the bundled fixture tree (it contains deliberately broken
links):

```shell
$ python -m linklattice examples/sample-docs
README.md
      11  error   missing-guide.md  |  target does not exist: missing-guide.md
      12  error   #does-not-exist  |  anchor #does-not-exist does not exist

api.md
       5  error   missing.html  |  target does not exist: missing.html
       7  error   Guide.md  |  target path letter-case does not match the file on disk: Guide.md
      11  error   assets/missing.png  |  target does not exist: assets/missing.png

guide.md
      11  warning assets/spec.pdf#details  |  anchor '#details' not verified: target is not a Markdown file
      13  error   ../outside/nope.md  |  target does not exist: ../outside/nope.md

Summary: 3 files scanned, 17 links checked, 6 errors, 1 warnings, 2 skipped in 0.02s
```

Exit code `1`. The same run with `--format json` (the committed artifact is
[`results/sample-report.json`](results/sample-report.json)):

```json
{
  "findings": [
    {
      "file": "README.md",
      "line": 11,
      "reason": "target does not exist: missing-guide.md",
      "severity": "error",
      "target": "missing-guide.md"
    },
    ...
  ],
  "summary": {
    "duration_seconds": 0.072,
    "errors": 6,
    "files_scanned": 3,
    "links_checked": 17,
    "root": "examples/sample-docs",
    "skipped": 2,
    "warnings": 1
  },
  "tool": {"name": "linklattice", "version": "0.1.0"}
}
```

`skipped` is 2: one external `https://` link (skipped by default) and one
target suppressed by the `allow` list in
[`examples/sample-docs/.linklattice.json`](examples/sample-docs/.linklattice.json).
The `drafts/` folder is excluded by the same file, which is why only 3 files
were scanned.

## Architecture summary

```
cli.py ──> scanner.py (file discovery + .linklattice.json config)
   │             │
   └──────> checks.py ──> markdown.py (link extraction, code-fence aware)
                    │            └──> anchors.py (GitHub slugger)
                    v
               report.py (text / json renderers)
```

`markdown.py` masks fenced blocks, front matter and code spans before running
four regexes per line; `anchors.py` turns heading text into GitHub slugs and
de-duplicates them; `checks.py` classifies and validates every target
(caching anchors per file); `report.py` renders. Full details in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Requirements

- Python **3.10+** (developed and tested on Python 3.14.3)
- Standard library only - no third-party packages, no network access, no
  build step for development use

## Installation

Development runs need no install; put `src/` on the import path:

```shell
# Windows PowerShell
$env:PYTHONPATH = "src"
python -m linklattice <path>

# POSIX
PYTHONPATH=src python -m linklattice <path>
```

If you do want the console script, the project ships a standard
`pyproject.toml`:

```shell
python -m pip install .
linklattice <path>
```

(This repository's validation environment is offline and has no `setuptools`
build backend, so that install path was **not** exercised here - see
[RESULTS.md](RESULTS.md). The `PYTHONPATH` path above is the one that was
actually run.)

## Quick start

```shell
$ $env:PYTHONPATH = "src"
$ python -m linklattice docs
Summary: 3 files scanned, 9 links checked, 0 errors, 0 warnings, 0 skipped in 0.21s
$ echo $LASTEXITCODE
0
```

That run is against this repository's own `docs/` folder: 9 links, no errors,
exit code 0.

## Usage examples

```shell
python -m linklattice docs                          # scan a folder
python -m linklattice README.md                     # scan a single file
python -m linklattice site --glob "*.mdx"           # custom glob
python -m linklattice site --exclude build          # repeatable excludes
python -m linklattice site --exclude "vendor/*" --exclude tmp
python -m linklattice docs --format json --no-summary > report.json
python -m linklattice docs --quiet                  # summary line only
python -m linklattice docs --allow "https://legacy/*"
python -m linklattice docs --check-external         # opt-in network checks
```

Full option reference: [docs/USAGE.md](docs/USAGE.md).

## Configuration

`.linklattice.json` at the scan root:

```json
{
  "exclude": ["vendor", "build/*"],
  "allow": ["legacy/*", "https://status.example/*"],
  "check_external": false
}
```

| Key | Type | Merge rule |
| --- | ---- | ---------- |
| `exclude` | list of strings | config entries first, then CLI `--exclude` values |
| `allow` | list of strings | config entries first, then CLI `--allow` values |
| `check_external` | boolean | CLI `--check-external` / `--no-check-external` wins when supplied |

Unknown keys are ignored. Invalid JSON or a wrong type is a configuration
error and exits with code 2.

## Testing

The suite uses `unittest` from the standard library - `pytest` is not needed
and is not installed:

```shell
python -m unittest discover -s tests -v
```

Run from the project root. The test files insert `src/` on `sys.path`
themselves, so `PYTHONPATH` is optional for tests. One test
(`LiveNetworkTests`) performs a real HTTP request and is skipped unless
`LINKLATTICE_NET_TESTS=1` is set.

Observed on this machine: **93 tests, 92 run, 1 skipped, 0 failures, 0
errors** (`OK (skipped=1)`).

## Project structure

```
linklattice/
  README.md                     this file
  LICENSE                       MIT
  CHANGELOG.md
  CONTRIBUTING.md
  RESULTS.md                    observed validation results
  .gitignore
  pyproject.toml                metadata + console script, no deps
  src/linklattice/
    __init__.py
    __main__.py                 python -m linklattice
    cli.py                      argparse, config merge, exit codes
    scanner.py                  file discovery, .linklattice.json loading
    markdown.py                 link extraction, code-fence awareness
    anchors.py                  GitHub slugger + anchor collection
    checks.py                   validation logic
    report.py                   text + json renderers
  tests/
    _support.py                 temp-tree fixtures, in-process CLI runner
    test_anchors.py
    test_markdown.py
    test_checks.py
    test_cli.py
  docs/
    PROJECT_SPEC.md
    ARCHITECTURE.md
    USAGE.md
  examples/sample-docs/         fixture tree with deliberate breakage
  results/                      generated reports (committed)
  .github/workflows/ci.yml
```

## Limitations

- **Headings only.** Anchors come from ATX (`#`) and Setext headings plus
  explicit `id=` / `name=` attributes. Autolinks, footnotes, `<!-- -->`
  comment anchors and Markdown-extra heading attributes are not parsed.
- **GitHub slug dialect.** Other renderers (GitLab, MkDocs, Sphinx) generate
  different slugs; anchors valid there may be reported as missing here.
- **Indented code blocks** (4 spaces / tab) are *not* masked - only fenced
  blocks, front matter and inline code spans. A link inside an indented block
  would be checked.
- **One document, one file.** Link reference definitions are file-local, as in
  CommonMark. Definitions that are never used are still validated.
- **Nested/overlapping links** such as `[![alt](img)](page)` resolve the image
  but not the outer link (the inner match wins the overlap rule).
- **Case-mismatch detection** walks `os.listdir` per path component; on a
  case-sensitive file system a wrong-case link simply reports
  "does not exist", which is equally fatal but worded differently.
- **No HTTP caching, redirects policy tuning or auth.** `--check-external`
  does one HEAD (falling back to GET) per link with a 10s timeout.
- **Anchors on non-Markdown targets** (`file.pdf#part`) cannot be verified and
  are reported as warnings, not errors.

## Roadmap

Realistic, in rough priority order - none of this is done yet:

1. `--max-report N` / per-file caps for very large trees.
2. Optional `#`-fragment support in `--allow` (currently patterns match the
   whole raw target or the file path).
3. Config-file support for a custom glob (`"glob": "*.mdx"`) so the CLI flag
   is not required.
4. A `--baseline <file>` mode to ignore known-existing breakage.
5. Footnote reference checking and Markdown-extra heading attributes
   (`{: #custom-id }`).
6. Parallel file scanning for repos with thousands of documents.

## Security notes

- The default code path opens **no sockets**. `urllib.request` is only
  reachable through `--check-external`.
- The tool only ever reads files; it never writes, moves or deletes anything
  in the scanned tree.
- With `--check-external`, a URL found in a document is requested as-is. If
  you scan untrusted Markdown, that makes your machine issue an outbound
  request to a host someone else chose (and reveals your IP). Leave the flag
  off for untrusted input.
- Files are read as UTF-8 with `errors="replace"`, so a binary file named
  `*.md` cannot crash or hang the scan.
- Findings include the raw link text from the document; treat reports as
  document content if you share them.

## License

MIT - see [LICENSE](LICENSE).
