# GPT-15: cross-source match deduplication

Completed 2026-10-21 in `/Users/stephen/Downloads/cs2-pro-playbook`.

## Implementation

- `playbook/dedupe.py::match_signature`: map + sorted canonical team pair + full round-winner sequence ordered by `round_num`. Names use the existing `canonical_team` / `load_team_aliases` configuration. Winners are team identities, including reconstruction from CT/T ownership where needed; team order, recording IDs, and tick offsets do not affect this signature.
- Histories must have all expected consecutive rounds; winner counts must agree with available final scores. Unknown teams or insufficient histories receive no signature and stay separate.
- Legacy fallback when winners are unavailable: team-aligned final score + round count + each round duration rounded to 0.1 seconds, or end ticks converted through tick rate and rounded to seconds. Partial known winners remain part of the fallback key. No score-only deduplication. All 316 current demos have valid complete winner sequences; no fallback was used.
- `playbook/dedupe.py::deduplicate_tables` selects the HLTV copy first, then lexicographically first `demo_id`. `hltv_demo_ids` resolves provenance from actual `data/raw/hltv/` paths using the parser identity function, including multipart files. Numeric HLTV match IDs alone cannot establish source because archive copies have them too. Without the raw files, selection falls back to `demo_id` order.
- `playbook/export.py::export_site` filters **every** demo-keyed table immediately after loading, before plant cleanup, roster ordering, profiles, tactics, lineups, and heatmaps. It prints `deduplicated 27 duplicate demos`.
- `scripts/import_hltv.py`: documented the permitted export-only content deduplication choice. Import remains header-only. A header cannot establish the winner sequence or canonical per-round team membership; doing that correctly requires event/team decoding and duplicates work done by parsing. Differently named copies may still be imported and parsed, but export counts one.
- Parsed files are retained: SHA-256 checks confirmed all **3,792** parsed Parquet files unchanged. All 27 selected copies come from the HLTV tree. No changes to `web/`; frontend data sync was not run.

## Results by map

The full parsed set changes from **316 → 289** unique demos. The active-map export changes from **310 → 283**; six Overpass demos remain excluded by the existing active-pool setting.

| Map | Duplicate demos removed | Exported matches before → after | Falcons matches before → after | Falcons map wins before → after | Falcons map win rate before → after |
| --- | ---: | ---: | ---: | ---: | ---: |
| `de_ancient` | 4 | 47 → 43 | 13 → 11 | 6 → 5 | 46.15% → 45.45% |
| `de_anubis` | 4 | 28 → 24 | 14 → 10 | 12 → 8 | 85.71% → 80.00% |
| `de_dust2` | 7 | 70 → 63 | 27 → 23 | 18 → 15 | 66.67% → 65.22% |
| `de_inferno` | 4 | 51 → 47 | 12 → 9 | 8 → 6 | 66.67% → 66.67% |
| `de_mirage` | 6 | 63 → 57 | 17 → 13 | 9 → 7 | 52.94% → 53.85% |
| `de_nuke` | 2 | 51 → 49 | 9 → 8 | 4 → 4 | 44.44% → 50.00% |

Rates above are **map wins / matches**, not round win rates. Exported hub rates use the existing three-decimal rounding. Falcons counts refer to the existing `Falcons` / `falcons` profile. The configuration still treats `FLC` separately; this task does not expand team aliases. This explains why all-map removed counts can exceed the reductions in that profile.

Verified the post-export Falcons team profiles, team heatmaps, and `data/site/heatmap_teams.json` agree on match counts and hub map win rates. No discarded demo IDs remain in active-map team match lists.

## Spirit 8–13 on Mirage

There are **two real matches**, represented by three recordings. `F` = Falcons won the round; `S` = Spirit won the round.

| Recording | Winner sequence | Disposition |
| --- | --- | --- |
| `2395001_spirit-vs-falcons-m2-mirage` | `FFFFSSSSSFFSFFSSSSSSS` | Drop archive copy |
| `falcons-vs-spirit-m1-mirage` | `FFSSSSSSFSSSSSSFFFFFS` | Keep HLTV copy |
| `spirit-vs-falcons-m2-mirage` | `FFFFSSSSSFFSFFSSSSSSS` | Keep HLTV copy |

The first match is HLTV 2395001, build 10772; the distinct `falcons-vs-spirit-m1-mirage` recording is build 10924. Different sequences preserve both 8–13 results. Monte 13–10, Natus Vincere 7–13, and FURIA 13–8 each now occur once in the Falcons Mirage match list.

## Summary fingerprints

**Rewriting is needed to restore affected prose summaries.** Existing fingerprint checks in `playbook/insights.py::attach_summaries` correctly omit stale paragraphs; no manual removal or fingerprint changes were needed. After export, **78 of 124 configured entries are stale**, **46 still match**, and **76 previously attached paragraphs are now omitted**. Some entries were already stale before this export. Falcons summaries are stale on all six maps. Opponent statistics and map-wide comparison baselines can change even for teams without duplicate recordings.

| Map | Stale entries requiring refreshed summaries | Still current |
| --- | ---: | ---: |
| `de_ancient` | 10 | 8 |
| `de_anubis` | 10 | 3 |
| `de_dust2` | 15 | 8 |
| `de_inferno` | 16 | 9 |
| `de_mirage` | 14 | 7 |
| `de_nuke` | 13 | 11 |

To prepare updated briefs after this task:

```sh
.venv/bin/python scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
```

Then rewrite the stale entries from the refreshed facts, validate replies with `scripts/insight_text.py check <map> <reply.json>`, and export again. Summary rewriting was not part of this deduplication task; no summary configuration was edited. The session responsible for `web/` can sync the corrected `data/site` when ready.

## Verification

- `.venv/bin/python -m pytest -q` → **180 passed, 2 skipped in 12.67s**.
- New `tests/test_dedupe.py`: **20 passing tests**, covering aliases, reversed team/row order, CT/T winner mapping, source/tick independence, same score with different winner sequences, timing fallback, invalid histories, deterministic HLTV preference, every-table filtering, idempotence, multipart provenance, and export before aggregation using synthetic data.
- `.venv/bin/python -m playbook export` → **exit 0**, `deduplicated 27 duplicate demos`, six active maps exported to `data/site`.
- Post-export assertions checked map totals, Falcons counts/wins, team heatmaps and hub rates, both distinct Spirit games, the absence of retired IDs, stale-summary omission, and unchanged parsed-file hashes.
- This directory has no root Git metadata, so no Git diff/commit was available.

## Duplicate selection audit

Each dropped archive ID below retains the corresponding HLTV demo whose ID is the suffix after the numeric match-ID prefix. All raw and parsed source files remain on disk.

| Map | Dropped archive demo ID | Kept HLTV demo ID |
| --- | --- | --- |
| `de_ancient` | `2394208_falcons-vs-m80-m2-ancient` | `falcons-vs-m80-m2-ancient` |
| `de_ancient` | `2394219_falcons-vs-legacy-m2-ancient` | `falcons-vs-legacy-m2-ancient` |
| `de_ancient` | `2394899_falcons-vs-g2-m3-ancient` | `falcons-vs-g2-m3-ancient` |
| `de_ancient` | `2394975_falcons-vs-betboom-m2-ancient` | `falcons-vs-betboom-m2-ancient` |
| `de_anubis` | `2394991_natus-vincere-vs-falcons-m3-anubis` | `natus-vincere-vs-falcons-m3-anubis` |
| `de_anubis` | `2394999_falcons-vs-vitality-m1-anubis` | `falcons-vs-vitality-m1-anubis` |
| `de_anubis` | `2395001_spirit-vs-falcons-m1-anubis` | `spirit-vs-falcons-m1-anubis` |
| `de_anubis` | `2395002_furia-vs-falcons-m2-anubis` | `furia-vs-falcons-m2-anubis` |
| `de_dust2` | `2394219_falcons-vs-legacy-m1-dust2` | `falcons-vs-legacy-m1-dust2` |
| `de_dust2` | `2394225_falcons-vs-mouz-m2-dust2` | `falcons-vs-mouz-m2-dust2` |
| `de_dust2` | `2394228_falcons-vs-legacy-m4-dust2` | `falcons-vs-legacy-m4-dust2` |
| `de_dust2` | `2394982_falcons-vs-monte-m2-dust2` | `falcons-vs-monte-m2-dust2` |
| `de_dust2` | `2394991_natus-vincere-vs-falcons-m1-dust2` | `natus-vincere-vs-falcons-m1-dust2` |
| `de_dust2` | `2394999_falcons-vs-vitality-m3-dust2` | `falcons-vs-vitality-m3-dust2` |
| `de_dust2` | `2395001_spirit-vs-falcons-m3-dust2` | `spirit-vs-falcons-m3-dust2` |
| `de_inferno` | `2394208_falcons-vs-m80-m1-inferno` | `falcons-vs-m80-m1-inferno` |
| `de_inferno` | `2394982_falcons-vs-monte-m1-inferno` | `falcons-vs-monte-m1-inferno` |
| `de_inferno` | `2394999_falcons-vs-vitality-m2-inferno` | `falcons-vs-vitality-m2-inferno` |
| `de_inferno` | `2395002_furia-vs-falcons-m3-inferno` | `furia-vs-falcons-m3-inferno` |
| `de_mirage` | `2394225_falcons-vs-mouz-m1-mirage` | `falcons-vs-mouz-m1-mirage` |
| `de_mirage` | `2394228_falcons-vs-legacy-m3-mirage` | `falcons-vs-legacy-m3-mirage` |
| `de_mirage` | `2394982_falcons-vs-monte-m3-mirage` | `falcons-vs-monte-m3-mirage` |
| `de_mirage` | `2394991_natus-vincere-vs-falcons-m2-mirage` | `natus-vincere-vs-falcons-m2-mirage` |
| `de_mirage` | `2395001_spirit-vs-falcons-m2-mirage` | `spirit-vs-falcons-m2-mirage` |
| `de_mirage` | `2395002_furia-vs-falcons-m1-mirage` | `furia-vs-falcons-m1-mirage` |
| `de_nuke` | `2394228_falcons-vs-legacy-m1-nuke` | `falcons-vs-legacy-m1-nuke` |
| `de_nuke` | `2394975_falcons-vs-betboom-m1-nuke` | `falcons-vs-betboom-m1-nuke` |
