# GPT-13 HLTV 录像导入脚本（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook` (Python pipeline in `playbook/`, venv `.venv`). The Hugging Face archive is exhausted for Falcons, so the owner downloads match archives by hand from HLTV ("GOTV Demo" button on each match page) into `data/raw/hltv/`. Write the importer that turns those downloads into demos the existing pipeline parses.

## `scripts/import_hltv.py`
- Input: every `.rar`, `.zip`, `.gz`/`.bz2` (single demo) or loose `.dem` directly under `data/raw/hltv/` (or `--src DIR`).
- Extract archives into `data/raw/hltv/<archive-stem>/`. Try in order: `bsdtar -xf` (macOS libarchive, reads RAR4/RAR5 and zip), `unar`, `7z x`, Python `zipfile` for zip. If none can open a RAR, print one clear line telling the owner what to install. Keep the original archive unless `--delete-archives`.
- For each extracted `.dem`: read the header/map with the same library the pipeline uses (see `playbook/parse.py`, `playbook/multipart.py`), skip maps outside `ACTIVE_POOL` in `playbook/export.py`, and **skip duplicates**: a demo whose identity (`playbook.parse.demo_identity` or equivalent) is already in `data/parsed` or already imported. Multipart demos (`-p1`, `-p2`) must stay together in one folder so `playbook/multipart.py` stitches them.
- Print a summary table: archive → maps found → imported / duplicate / skipped (map not in pool) / failed (reason).
- `--dry-run` lists what would happen without extracting.
- Make sure `python -m playbook parse` (default input `data/raw`) picks up `data/raw/hltv/**` (check `_demo_paths` in `playbook/cli.py`; extend it if it is not recursive).

## Tests
`tests/test_import_hltv.py`: zip fixtures built in a tmp dir with dummy `.dem` files (mock the header reader), covering extract, pool filter, duplicate skip, multipart folder grouping, dry-run. Run `.venv/bin/python -m pytest -q` and make sure everything passes.

## Docs
Add a short "从 HLTV 补录像" section to `README.md` (Chinese): where to download, where to put files, the three commands (`import_hltv.py`, `playbook parse`, `playbook export`).

## Rules
Do not touch `web/`, `.github`, `delegation/design-skills/`, or existing raw data. No network access is needed.

## Deliverable
Edit in place; write `delegation/GPT-13_report.md` (changed files, test result, which extractor works on this Mac — check `bsdtar --version` and whether it opens RAR5).
