# GPT-13 HLTV import report

Completed in `/Users/stephen/Downloads/cs2-pro-playbook`.

## Changed files

- `scripts/import_hltv.py`: imports top-level RAR, ZIP, gzip, bzip2 and loose demo downloads; supports `--src`, `--dry-run`, and `--delete-archives`. Reads `awpy.Demo.header['map_name']`, filters against `playbook.export.ACTIVE_POOL`, and deduplicates using `playbook.parse.demo_identity` against parsed parquet filenames, existing raw demos, and imports in the current batch. Loose imports are recorded in `.import_hltv.json` for subsequent runs.
- `playbook/cli.py::_demo_paths`: recursion already existed. Discovery now requires actual files, preventing a `game.dem/` directory created from `game.dem.gz` from being parsed as a demo. Case-insensitive demo extensions are supported, including explicit multipart sibling discovery.
- `tests/test_import_hltv.py`: 20 synthetic tests covering extraction, filtering, parsed/raw/batch/rerun duplicates, multipart grouping and invalid sequences, dry-run immutability, loose files, gzip/bzip2, extraction fallbacks, Homebrew `7zz`, header failures, no overwrite, partial-copy rollback, unsafe ZIP paths, and top-level-only download discovery. Header reads are mocked; no network or real downloads are required.
- `README.md`: added Chinese “从 HLTV 补录像” instructions with download location, the three pipeline commands, flags, extractors, and loose-file handling.
- `delegation/GPT-13_report.md`: this report.

Archive extraction is staged in temporary directories. Only eligible new demos are copied into `<source>/<archive-stem>/`, preserving nested directories and multipart grouping. A failed multipart copy rolls back its newly created files. Originals are retained by default; explicit archive deletion occurs only for an archive with no failures. Summary counts represent games/maps, not individual recording parts. A dry run never extracts or writes, so archive map/duplicate checks are explicitly deferred.

## Validation

Final required command:

```text
.venv/bin/python -m pytest -q
160 passed, 2 skipped in 14.26s
```

Focused importer command: `.venv/bin/python -m pytest -q tests/test_import_hltv.py` → **20 passed**.
CLI smoke check: `.venv/bin/python scripts/import_hltv.py --help` → successful.

## Extractor on this Mac

`command -v bsdtar unar 7z 7zz` found only `/usr/bin/bsdtar`.

```text
bsdtar --version
bsdtar 3.5.3 - libarchive 3.7.4 zlib/1.2.12 liblzma/5.4.3 bz2lib/1.0.8
```

Verified RAR5 extraction offline: generated a minimal stored RAR5 archive in a temporary directory, with RAR5 signature `526172211a070100` and valid header/payload CRCs, then ran `bsdtar -xf <probe.rar> -C <temporary-output>`. Exit status **0**, empty stderr, and the extracted `probe.dem` matched the original payload byte for byte. Native ZIP extraction also passed the importer fixtures. No existing HLTV RAR was available for testing; this verifies stored RAR5 support, not every compressed/encrypted RAR variant.

Fallback order: `bsdtar`, `unar`, `7z` (or Homebrew's `7zz`), then Python `zipfile` for ZIP. If no RAR extractor succeeds, the summary prints one install hint: `brew install sevenzip`.

## Operational notes

- Loose `.dem` files are inspected/registered in place and never removed. Rejected or duplicate loose originals remain recursively discoverable by `playbook parse`; move unwanted originals outside `data/raw/` to exclude them. Archive-rejected demos are never published.
- `--src` outside `data/raw/` requires passing that directory to `python -m playbook parse DIR`.
- No edits were made to `web/`, `.github`, `delegation/design-skills/`, or existing raw data. Extraction probes and test fixtures used temporary directories. No network access or package installation was used.
- The checkout has no Git metadata, so changes were made in place without a Git diff or commit.
