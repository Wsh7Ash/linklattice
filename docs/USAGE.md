# Usage

## Invocation

There is no install step required. From the project root:

```shell
# Windows PowerShell
$env:PYTHONPATH = "src"
python -m linklattice <path>

# POSIX
PYTHONPATH=src python -m linklattice <path>
```

If the package is installed (see README), the `linklattice` console script is
equivalent.

`<path>` is a directory to scan recursively, or a single Markdown file.

## Options

```
usage: linklattice [-h] [--glob PATTERN] [--exclude PATTERN] [--allow PATTERN]
                   [--format {text,json}]
                   [--check-external | --no-check-external] [--quiet]
                   [--no-summary] [--version]
                   [path]
```

| Option | Effect |
| ------ | ------ |
| `--glob PATTERN` | File name glob to scan. Default `*.md`. A pattern containing `/` is matched against the whole relative path. |
| `--exclude PATTERN` | Skip matching paths. Repeatable. Glob patterns are matched with `fnmatch`; anything else is a substring match on the relative path. |
| `--allow PATTERN` | Suppress findings whose raw target matches. Repeatable. Glob or substring. Suppressed links are counted as skipped. |
| `--format text\|json` | Report format. Default `text`. JSON output is a single document with nothing after it. |
| `--check-external` / `--no-check-external` | Turn HTTP verification on/off. Off by default; the CLI flag wins over `.linklattice.json`. |
| `--quiet` | Print only the summary line (text format). |
| `--no-summary` | Omit the summary line; with `--format json` the `summary` key is dropped. |
| `--version` | Print the version and exit 0. |

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | No error findings. Warnings may be present. |
| 1 | At least one error finding. |
| 2 | Usage or configuration error (missing path, unparseable config, bad flag). |

## Examples

Check a documentation folder:

```shell
python -m linklattice docs
```

Check one file:

```shell
python -m linklattice README.md
```

Only reStructuredText-adjacent Markdown with a different extension, skipping
generated trees:

```shell
python -m linklattice site --glob *.mdx --exclude build --exclude "vendor/*"
```

Machine-readable output for CI:

```shell
python -m linklattice docs --format json --no-summary > report.json
echo $?
```

Summary-only gate in a script:

```shell
python -m linklattice docs --quiet
```

Verify external links as well (this is the **only** mode that touches the
network):

```shell
python -m linklattice docs --check-external
```

## Configuration file

Place `.linklattice.json` at the scan root:

```json
{
  "exclude": ["vendor", "build/*"],
  "allow": ["https://status.example/*", "legacy/*"],
  "check_external": false
}
```

- `exclude` / `allow` are lists of strings. Config entries and CLI flags are
  merged: config first, then the CLI values are appended.
- `check_external` is a boolean. The CLI flag wins when it is supplied.
- Unknown keys are ignored; a wrong type or invalid JSON is a configuration
  error (exit code 2).

## What is checked

| Target kind | Example | Behaviour |
| ----------- | ------- | --------- |
| External | `https://…`, `mailto:…` | Skipped by default (counted as `skipped`); checked with `--check-external`. |
| Absolute path | `/img/logo.png` | Existence is checked on the file system. |
| In-page anchor | `#usage` | Resolved against this file's heading slugs. |
| Relative file | `../api.md` | Existence plus letter-case check. |
| Relative + anchor | `guide.md#install` | File must exist and the anchor must resolve in that file. |
| Anchor on non-Markdown | `spec.pdf#part` | Reported as a warning: it cannot be verified. |

Link-looking syntax inside fenced code blocks, YAML front matter and inline
code spans is ignored, for links and for headings alike.

## Report format

Text output groups findings by file:

```
README.md
      11  error   missing-guide.md  |  target does not exist: missing-guide.md

Summary: 3 files scanned, 17 links checked, 6 errors, 1 warnings, 2 skipped in 0.07s
```

JSON output has three top-level keys: `findings`, `summary` and `tool`. Every
finding has `file`, `line`, `target`, `reason` and `severity`.

## Counting rules

- `files_scanned` - Markdown files that were opened.
- `links_checked` - every link reference triaged, including the ones that were
  then skipped as external or allow-listed.
- `skipped` - external links and allow-listed targets that were deliberately
  not validated.
- `errors` / `warnings` - findings by severity.

## See also

- [Project spec](PROJECT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Severity model](ARCHITECTURE.md#severity-model)

