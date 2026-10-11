# Architecture

`linklattice` is a small pipeline: discover files -> extract links -> validate
-> render. Each stage lives in its own module and only talks to the next
through plain dataclasses.

```
cli.py ──> scanner.py (discover + config)
   │             │
   │             v
   └──────> checks.py ──> markdown.py (extract)  ──> anchors.py (slugger)
                    │
                    v
               report.py (text / json)
```

## Modules

### `cli.py`

Argument parsing with `argparse` and exit-code policy.

| Exit code | Meaning                                                        |
| --------- | -------------------------------------------------------------- |
| 0         | scan completed, no error findings (warnings allowed)            |
| 1         | scan completed, at least one error finding                      |
| 2         | usage or configuration problem (missing/unknown path, bad config, bad flag) |

The CLI is the only place that reads `.linklattice.json` values and merges
them with flags: `exclude` and `allow` lists are concatenated (config first,
CLI appended), while `check_external` is a scalar, so the CLI value wins when
the flag is present at all (`--check-external` / `--no-check-external`).

`--format json` writes exactly one JSON document and nothing else, so stdout
can be piped straight into a parser. The text format groups findings by file
and optionally ends with a summary line (`--quiet` keeps only that line,
`--no-summary` drops it).

### `scanner.py`

- `load_config(root)` reads `.linklattice.json`, validates types and raises
  `ConfigError` (-> exit 2) on malformed content. Unknown keys are ignored.
- `discover_files(root, pattern, excludes)` walks the tree with `os.walk`,
  applies the glob to the relative posix path (or the file name when the
  pattern has no separator) and the exclude filter, and returns
  `(absolute_path, relative_posix_path)` pairs. A single file may be passed
  as the scan root.
- Exclude patterns with glob characters are `fnmatch`-ed against the relative
  path and the file name; anything else is a substring match, so
  `--exclude node_modules` behaves the way people expect.

### `markdown.py`

Pure text processing, no I/O.

- `mask_fenced(text)` blanks YAML front matter and fenced code blocks - triple
  backtick or triple tilde, any indentation, and a backtick fence's info
  string may not itself contain backticks - while preserving line numbers, so
  a `# comment` inside a shell block can never become a heading and
  `[x](y.md)` inside a block can never become a link.
- `strip_code_spans(line)` blanks `code` spans in place, preserving columns.
- `extract_links(text)` runs four regexes per line - inline links/images,
  reference definitions, reference usages, HTML `href`/`src` - sorts the
  matches by column and drops overlaps, so `[![alt](img)](page)` cannot
  double-count.

The result carries a `definitions` table (normalized label -> raw target) that
lets `checks.py` resolve `[text][label]`. An undefined label is plain text in
CommonMark, so it is deliberately ignored rather than flagged.

### `anchors.py`

- `slugify(text)`: lowercases, removes code/emphasis markers, strips
  everything that is not a unicode word character, whitespace or hyphen
  (underscores survive), then turns spaces into hyphens.
- `collect_anchors(text)`: walks the masked file collecting ATX headings,
  Setext headings (`text` over `===` / `---`), and explicit `id=` / `name=`
  attributes, then de-duplicates with GitHub's `-1`, `-2`, ... suffixes.
  Front matter is masked first, so `title: My Doc` above a `---` never becomes
  an anchor.

### `checks.py`

The only module that touches the file system (and, opt-in, the network).

- Classifies each target: scheme or `//` -> external; leading `#` -> in-page
  anchor; leading `/` -> absolute; otherwise relative, with the fragment split
  off after percent-decoding.
- Existence check, then a letter-case check: `_case_mismatch()` walks the path
  component by component with `os.listdir`, so a link to `README.md` that
  resolves to `readme.md` is reported even on a case-insensitive file system.
- Anchors are checked against `collect_anchors()` of the current file or of
  the target file (cached per run). An anchor pointing at a non-Markdown file
  cannot be verified and is reported as a warning instead of an error.
- Reference findings are de-duplicated by `(file, target)`, so a broken
  definition referenced from five places produces one finding.
- `http_status()` is the sole network entry point. It is only called when
  `check_external` is true; the default path never reaches it.

### `report.py`

`render_text()` groups findings by file; `render_json()` emits a document with
a stable shape and sorted keys:

```json
{
  "findings": [{"file": "...", "line": 1, "reason": "...", "severity": "error", "target": "..."}],
  "summary": {"duration_seconds": 0.0, "errors": 0, "files_scanned": 0,
              "links_checked": 0, "root": "...", "skipped": 0, "warnings": 0},
  "tool": {"name": "linklattice", "version": "0.1.0"}
}
```

Only `duration_seconds` (and `root`, if the caller passes an absolute path)
varies between runs; keys and structure do not.

## Severity model

| Severity | Used for                                                            |
| -------- | ------------------------------------------------------------------- |
| error    | broken local target: missing file, case mismatch, missing anchor     |
| warning  | skipped/ambiguous: anchor on a non-Markdown file, empty target, unreachable external link with `--check-external` |

Warnings never affect the exit code.

## Data flow types

```python
Link(line, target, kind, is_image)          # markdown.py
Extraction(links, definitions)              # markdown.py
Finding(file, line, target, reason, severity)  # checks.py
Result(findings, files_scanned, links_checked, skipped, duration)  # checks.py
Config(exclude, allow, check_external, source)  # scanner.py
```

## See also

- [Project spec](PROJECT_SPEC.md)
- [Usage](USAGE.md)

