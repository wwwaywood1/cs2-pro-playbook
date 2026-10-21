# GPT-15 跨来源重复比赛去重（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook` (Python pipeline, `.venv`). Another Codex session edits `web/` — do not touch `web/`.

## Problem (found by MiniMax data QA, confirmed by Claude)
The same real match is parsed twice when it exists both in the Hugging Face archive (`data/raw/cs2povarchive/...`) and in an HLTV download (`data/raw/hltv/...`): the files differ, so `demo_id` differs and the importer's identity check does not catch it. Example: `data/site/de_mirage/teams/falcons.json` › `matches` has 17 rows but (Monte 13-10), (Natus Vincere 7-13), (FURIA 13-8) appear twice and (Spirit 8-13) three times. Dust2 has the same issue. All per-team/per-player/tactics aggregates are inflated.

## Fix
1. Content signature per parsed demo: map + sorted pair of team names (after alias normalisation used by the pipeline) + the full round-winner sequence (or, if unavailable, final score + round count + per-round end ticks/durations rounded). Two demos with the same signature are the same match.
2. **Export**: drop duplicates deterministically before any aggregation (prefer the HLTV GOTV copy when both exist, else the first by demo_id), and print a one-line summary `deduplicated N duplicate demos`. Keep parsed files on disk (no deletion).
3. **Importer** (`scripts/import_hltv.py`): after extraction, skip a demo whose signature already exists in `data/parsed` (needs a quick parse of rounds, or compare after parse — choose the cheaper correct option and document it). If signature needs parsing, it is acceptable to only dedupe at export.
4. Also check: Spirit 8-13 appearing three times — verify whether it is really one match or two different matches with the same score (different round sequences ⇒ keep both).
5. Tests: unit tests for the signature and export de-duplication (synthetic tables), including "same score, different round sequence ⇒ not duplicate". Run `.venv/bin/python -m pytest -q`, then `.venv/bin/python -m playbook export`.

## Deliverable
Write `delegation/GPT-15_report.md`: how the signature works, how many duplicates were removed per map, Falcons' per-map match counts and map win rates before → after, and whether the summaries need rewriting (their fingerprints will drop stale ones automatically).
