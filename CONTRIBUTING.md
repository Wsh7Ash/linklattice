# Contributing

Thanks for considering a contribution to `linklattice`.

## Ground rules

- Standard library only. No third-party runtime or test dependencies.
- Python 3.10+ syntax; the project is developed and tested on Python 3.14.
- The default code path must never perform network I/O. Anything that touches
  the network has to live behind the `--check-external` flag.
- No placeholders or TODO stubs in core functionality.

## Development setup

No install is required:

```shell
# Windows PowerShell
$env:PYTHONPATH = "src"
python -m linklattice path/to/docs

# POSIX
PYTHONPATH=src python -m linklattice path/to/docs
```

## Running the tests

From the project root:

```shell
python -m unittest discover -s tests -v
```

The suite inserts `src/` on `sys.path` itself, so `PYTHONPATH` is optional
for tests. One test (`LiveNetworkTests`) is skipped unless
`LINKLATTICE_NET_TESTS=1` is set, because it performs a real HTTP request.

## Adding a feature or fix

1. Add or extend a test in `tests/` first - the suite must stay green.
2. Keep reports ASCII-only so output is portable across terminals.
3. Update `CHANGELOG.md` under an `Unreleased` heading.
4. Keep `docs/` in sync with any user-visible behaviour change.

## Report format stability

`--format json` is a machine interface. Only add keys, never rename or remove
them within the same minor version.
