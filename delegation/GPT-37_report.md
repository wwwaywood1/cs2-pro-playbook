# GPT-37 team and player aliases report

Completed items 1–3 of `delegation/GPT-37_aliases.md`. Reviewed and retained the interrupted run's alias implementation; expanded integration coverage and completed a fresh export and preview copy.

## Team aliases and slugs

`config/team_aliases.csv` now includes these mappings and canonical self-entries:

| Alias | Canonical | Logo/URL slug |
| --- | --- | --- |
| 100T | 100 Thieves | `100-thieves` |
| OG CS2 | OG | `og` |
| SINNERS ESPORT | SINNERS | `sinners` |
| Inner Circle Esports | Inner Circle | `inner-circle` |

All **46 existing canonical slugs remain unchanged**. Checks: `_sync/gpt37/team-slug-check.json` and `_sync/gpt37/output-check.json`.

## Donk same-round check

Before applying aliases, checked every round-keyed Steam ID column in raw parsed loadouts, positions, kills (attacker/victim/assister), plants, utility, shots and player rounds. The identity key was `(demo_id, round_num)`, across all parsed maps before content dedupe. **Zero rounds contain both IDs.** Both IDs are labeled `donk` / `Spirit`; the alias occurs in exactly **59 rounds**:

| Demo ID | Alias rounds |
| --- | --- |
| hltv-5fa047017033f754_spirit-vs-liquid-m2-dust2 | 24 |
| hltv-f868fdc74b8deb31_spirit-vs-falcons-m1-anubis | 17 |
| hltv-f868fdc74b8deb31_spirit-vs-falcons-m2-mirage | 18 |

Raw main-ID presence: **3,118 rounds**. After removing **52 duplicate recordings**, the main ID has **2,781 rounds**, and the alias adds **59**, totaling **2,840**. This is a dataset identity check; no name-based merges were inferred. Reproducible command: `.venv/bin/python _sync/gpt37/audit_inputs.py`; evidence: `_sync/gpt37/identity-check.json`.

## Export behavior and tests

- `config/player_aliases.csv`: `76561198018303780` → `76561198386265483`.
- `playbook/config.py:load_player_aliases` loads verified mappings. `playbook/dedupe.py:apply_aliases` replaces `steamid` and every `*_steamid` column before export aggregation, preserving integer/string types, nulls and source parsed files.
- `playbook/export.py:export_site` supplies these canonical tables to profiles, rosters, heatmaps, tactics, radar6, WPA and replays. Replay player lists contain display metadata and positional indices; their schema remains unchanged.
- `tests/test_player_aliases.py` covers all identity columns, type/null preservation, idempotence, stable slugs, and a real derived-view export with two source IDs. Only model probabilities and unrelated team profiles are stubbed; profile/radar/WPA/replay builders run.

## Exported Spirit roster

From `data/site/heatmap_teams.json`, including retained historical maps: **five players**.

| Name | Steam ID | Rounds |
| --- | --- | --- |
| donk | 76561198386265483 | 2840 |
| magixx | 76561199063238565 | 2840 |
| sh1ro | 76561198081484775 | 2840 |
| tN1R | 76561198872013168 | 2840 |
| zont1x | 76561198995880877 | 2840 |

Across the whole deduplicated dataset, **no other roster with >5 IDs has a name shared by multiple IDs** (all observed names, case-insensitive, whitespace trimmed). No additional player aliases were added. Evidence: `_sync/gpt37/roster-audit.json`.

## Export, preview and validation

```sh
caffeinate -i .venv/bin/python -u -m playbook export
cp -R data/site/. site-preview/data/
caffeinate -i .venv/bin/python -m pytest -q
.venv/bin/python _sync/gpt37/audit_outputs.py
```

- The pre-sleep exporter had resumed after wake. Both export processes have exited; the fresh run returned exit 0. Repeated the preview copy and checks after both exited.
- Export completed successfully: **7 active maps / 514 map demos**; generated `2026-10-24T04:28:38+00:00`. Log: `_sync/gpt37/export.log`.
- Archived **44 obsolete generated team files** (22 per tree) for the four superseded slugs after confirming canonical replacements. Backups: `_sync/gpt37/stale-outputs/`; manifest: `_sync/gpt37/stale-output-archive.json`.
- Preview: **3509 current export files compared by SHA-256; zero mismatches**. The requested overlay preserves **2733 pre-existing extra preview files**, including an older nested `site/` snapshot; these are listed in `_sync/gpt37/output-check.json`.
- No alias Steam ID remains anywhere in either output tree. Donk's per-map profile, radar6 and WPA round counts agree; exported replays for the alias demos contain one Spirit donk.
- Full pytest: **285 passed, 3 skipped, 1 warning in 17.30s**; alias tests: **11 passed**. Logs: `_sync/gpt37/pytest.log`, `_sync/gpt37/pytest-aliases.log`. The sole warning is joblib's existing macOS physical-core detection fallback.

No remaining GPT-37 work. This directory has no `.git`; source review used the preserved `_sync/gpt37/before/` baseline.
