# Results

## Environment

- OS: Microsoft Windows 10 IoT Enterprise LTSC 10.0.19044 (AMD64), PowerShell 7.6.0
- Runtime/compiler: CPython 3.14.3 (`Python 3.14.3 (main, Feb 5 2026, 13:35:35) [MINGW GCC 15.2.0 64 bit (AMD64)]`)
- Dependency manager: none / stdlib only (no `pip install` performed; `ruff`, `mypy`, `pylint`, `black`, `build`, `setuptools` are not installed in this environment)

## Validation performed

- install: FAIL
- build: N/A
- unit tests: PASS
- integration tests: N/A
- lint: N/A
- type check: N/A
- demo run: PASS

## Commands executed

```shell
# 1. unit test suite (from the project root, PYTHONPATH optional for tests)
python -m unittest discover -s tests -v
#   -> Ran 93 tests in 0.507s
#   -> OK (skipped=1)
#   -> exit 0

# 2. same suite with PYTHONPATH=src explicitly
$env:PYTHONPATH = "src"; python -m unittest discover -s tests -v
#   -> Ran 93 tests in 0.936s
#   -> OK (skipped=1)
#   -> exit 0

# 3. demo run against the bundled fixture tree
$env:PYTHONPATH = "src"; python -m linklattice examples/sample-docs
#   -> exit 1 (6 errors), output pasted below

# 4. generate the committed report artifacts
$env:PYTHONPATH = "src"; python -m linklattice examples/sample-docs > results/sample-report.txt
$env:PYTHONPATH = "src"; python -m linklattice examples/sample-docs --format json > results/sample-report.json
#   -> both exit 1, files written

# 5. JSON stability: two runs compared with the duration field normalised
python -m linklattice examples/sample-docs --format json   # run twice
#   -> identical_except_duration=True

# 6. dogfood run over this repository's own docs
$env:PYTHONPATH = "src"; python -m linklattice docs
#   -> Summary: 3 files scanned, 9 links checked, 0 errors, 0 warnings, 0 skipped in 0.21s
#   -> exit 0

# 7. dogfood run over the whole repository, excluding the intentionally broken fixtures
$env:PYTHONPATH = "src"; python -m linklattice . --exclude examples
#   -> Summary: 6 files scanned, 17 links checked, 0 errors, 0 warnings, 2 skipped in 0.20s
#   -> exit 0

# 8. usage / version paths
$env:PYTHONPATH = "src"; python -m linklattice --help     # exit 0
$env:PYTHONPATH = "src"; python -m linklattice --version  # "linklattice 0.1.0", exit 0
$env:PYTHONPATH = "src"; python -m linklattice            # "error: a path to scan is required", exit 2

# 9. install attempts (recorded honestly - both failed in this offline environment)
python -m pip install -e . --no-build-isolation --no-index
#   -> exit 1: "externally-managed-environment" (PEP 668) - system Python refuses installs
python -m venv <temp>/llvenv
<temp>/llvenv/bin/python -m pip install -e . --no-index
#   -> exit 1: "Could not find a version that satisfies the requirement setuptools>=61 (from versions: none)"
<temp>/llvenv/bin/python -m pip install -e . --no-build-isolation --no-index
#   -> exit 2: BackendUnavailable: Cannot import 'setuptools.build_meta'
#   -> importlib check: "No module named 'setuptools'"
```

## Observed result

**Unit tests: 93 tests, 92 executed, 1 skipped, 0 failures, 0 errors** -
`Ran 93 tests in 0.507s` / `OK (skipped=1)`, exit code 0. The single skip is
`test_cli.LiveNetworkTests.test_real_head_request`, which is gated behind
`LINKLATTICE_NET_TESTS=1` because it would perform a real HTTP request.
Every other test runs offline; the "no network by default" test patches
`linklattice.checks.http_status` with a mock that raises and asserts it is
never called.

**Demo run** (`python -m linklattice examples/sample-docs`, exit code 1):

```
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

Counting: 17 links triaged; 2 skipped (one `https://` link, one target
suppressed by the `allow` list in `examples/sample-docs/.linklattice.json`);
`drafts/` excluded by the same config file, which is why only 3 of the 4
fixture documents were scanned.

**Dogfood run over `docs/`** (exit code 0):

```
Summary: 3 files scanned, 9 links checked, 0 errors, 0 warnings, 0 skipped in 0.21s
```

This run found two real bugs during development: `../README.md` did not exist
yet, and a line in `ARCHITECTURE.md` beginning with `~~~` opened an unclosed
CommonMark code fence that swallowed the rest of the file. Both were fixed.

**JSON report excerpt** (from `results/sample-report.json`):

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

Two consecutive `--format json` runs produced byte-identical output after
normalising `duration_seconds` (`identical_except_duration=True`).

**Install:** not achievable here. The environment has no network and no
`setuptools` build backend, and the system interpreter is marked
externally-managed (PEP 668). The project therefore runs from source with
`PYTHONPATH=src`, which is the path exercised by every command above. The
`pyproject.toml` console-script entry point is declared but unverified.

## Generated artifacts

- `results/sample-report.txt` - text report for `examples/sample-docs/`
  (7 findings + summary, 718 bytes at generation time)
- `results/sample-report.json` - the same run as machine-readable JSON
  (7 findings, 1631 bytes at generation time)

Both artifacts were produced by commands 3-4 above and are committed as-is;
the `root` field is a relative path (`examples/sample-docs`), so no absolute
machine path appears in them.

## Known limitations

- Anchor slugs follow GitHub's dialect; GitLab/MkDocs/Sphinx slugs differ.
- Indented (4-space) code blocks are not masked - only fenced blocks, YAML
  front matter and inline code spans.
- Setext headings are supported, but heading attributes
  (`## Title {#custom}`) and footnotes are not parsed.
- `[![alt](img)](page)` resolves the image but not the outer link.
- The case-mismatch reason string differs by file system: on a
  case-sensitive system the same fixture reports "does not exist" instead of
  "letter-case does not match".
- `--check-external` performs one HEAD (GET fallback) per link with a 10s
  timeout; no caching, no redirect policy tuning, no authentication.
- `install`, `build`, `lint` and `type check` could not be exercised in this
  offline environment (no `setuptools`, `build`, `ruff`, `mypy`, `pylint` or
  `black` available) and are recorded as FAIL / N/A rather than assumed.
