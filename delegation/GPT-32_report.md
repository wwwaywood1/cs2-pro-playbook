# GPT-32 Vitality ingest report

## Result

- Found **63** Vitality archives (43,308,675,049 bytes) directly in `/Users/stephen/Downloads`; all archive listings were readable.
- **61** archives newly moved into `data/raw/hltv/`; **2** existing same-name destinations were preserved, with the downloaded copies left in Downloads by `mv -n`.
- Explicitly staged the single-map `esports-world-cup-2026-vitality-vs-100-thieves-nuke-xgmnZlKoCUg1rSdM6g5Q-g.rar`, which does not match the refresh script’s `-bo[135]-` glob.
- Ran `bash scripts/refresh.sh` unchanged. Its “moved 62” line includes two `mv -n` no-ops; actual automatic moves were 60, plus the one manual move.
- Selected-archive demo/game totals: **114 imported**, **25 duplicate skips**, **16 off-pool skips**, **0 import failures**. 58 archives contributed imports; 5 contributed none.
- Newly parsed match rows: **107**; new rows retained after content dedupe: **107**.
- Observed production source/config hash differences: **config/events.json**. This ingest agent made no production code/config edits. `config/events.json` was updated concurrently (mtime 2026-10-22 22:55:03 local), adding schedules; those changes were preserved and used by export. Audit helpers and logs are under `_sync/gpt32/`.

## Stage wall times

Seconds measured by a temporary Bash environment wrapper around the exact Python invocations; production scripts were not modified. The automatic move stage completed within the first second (import began at shell second 0); the earlier single-archive manual staging command was not timed separately.

```text
SHELL_START 0
START 0 scripts/import_hltv.py
END 1520 elapsed=1520 rc=0 scripts/import_hltv.py
START 1520 -m playbook parse
END 3099 elapsed=1579 rc=1 -m playbook parse
START 3099 -m playbook export
END 3765 elapsed=666 rc=0 -m playbook export
START 3765 scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
END 3765 elapsed=0 rc=0 scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
```

## Vitality maps before → after

Counts come from `data/site/<map>/teams.json`; baseline copies are in `_sync/gpt32/site-before/`.

| Map | Before | After | Delta |
| --- | --- | --- | --- |
| de_ancient | 0 | 2 | 2 |
| de_anubis | 3 | 16 | 13 |
| de_cache | 0 | 8 | 8 |
| de_dust2 | 3 | 29 | 26 |
| de_inferno | 3 | 19 | 16 |
| de_mirage | 4 | 22 | 18 |
| de_nuke | 2 | 19 | 17 |
| de_overpass | 1 | 1 | 0 |

- Active-pool total: **15 → 115** maps.
- Including retained historical Overpass JSON: **16 → 116**. Overpass is outside `ACTIVE_POOL`; its existing export is not rewritten or removed by this refresh.
- Active-pool dated coverage: **2026-01-12 → 2026-10-03**. This is the available estimated/manual date range, not proof that every archive has a date or that a full year is covered.
- Active-pool Vitality map-row date precision: `{'event': 112, 'null': 2, 'day': 1}`; newly parsed map rows before dedupe: `{'event': 106, 'null': 1}`. `day` means HLTV-ID rank interpolation within a configured event, `event` means the event start, and `exact` means a CSV override.

- Cache is in `playbook.export.ACTIVE_POOL`, but `config/maps/de_cache.toml` is absent. New Cache data uses `playbook.config.load_map` fallback metadata (empty callout/region mapping and a default radar transform); review map metadata before treating those tactical/radar outputs as complete.

## Missing event schedules and date gaps

At initial inspection, the nine archive-derived event slugs listed below were absent from `config/events.json`. A concurrent external update added all nine, plus a Krakow spelling alias, before export. **No archive-derived event slugs are currently missing from the registry.** This ingest agent did not edit or invent event dates. The existing Virtus.pro path-to-event lookup gap still leaves a newly imported map undated.

Counts below are published, parsed map rows (unique demo IDs) and series/archive counts. Off-pool and identity-collision skips are excluded. Initial null-date counts are reconstructed against the ten event entries recorded in the first terminal read (`_sync/gpt32/events-at-initial-inspection.json`); final counts use the configuration actually used by export. HLTV IDs are listed only when present in parsed metadata.

### `blast-bounty-2026-season-1` — BLAST Bounty 2026 Season 1 (online)

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **2**.
- Archives/series: **2**; parsed map rows: **2** (2 new); date null: **1**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **1**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `blast-bounty-2026-season-1-eyeballers-vs-vitality-bo3-cdixknqTHEiRBWJBE_PGSN.rar`
  - `blast-bounty-2026-season-1-virtuspro-vs-vitality-bo3-q1MsDOb5aD1l3u9zoYMQdQ.rar`

### `blast-bounty-2026-season-1-finals` — BLAST Bounty 2026 Season 1 Finals

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **4**.
- Archives/series: **2**; parsed map rows: **4** (4 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `blast-bounty-2026-season-1-finals-gamerlegion-vs-vitality-bo3-xvrJ9muhRij9eX0sOLSDM4.rar`
  - `blast-bounty-2026-season-1-finals-vitality-vs-falcons-bo3-m75xkiVwc3YZkEbdtP1s9_.rar`

### `blast-open-rotterdam-2026` — BLAST Open Rotterdam 2026

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **8**.
- Archives/series: **5**; parsed map rows: **8** (8 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `blast-open-rotterdam-2026-parivision-vs-vitality-bo3-hiwqXfBGRevcYWe8xgLMbB.rar`
  - `blast-open-rotterdam-2026-the-mongolz-vs-vitality-bo3-7AUu3EcXrnLd4gicqzNp8L.rar`
  - `blast-open-rotterdam-2026-vitality-vs-9z-bo3-kVsrbfS7P7ANQA8A6NP-eu.rar`
  - `blast-open-rotterdam-2026-vitality-vs-aurora-bo3-FlxFvdx4Pl-M44Zsyy4BH3.rar`
  - `blast-open-rotterdam-2026-vitality-vs-natus-vincere-bo5-M1X_ekEYL-WVFzIqhTKs9U.rar`

### `blast-rivals-2026-season-1` — BLAST Rivals 2026 Season 1

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **7**.
- Archives/series: **4**; parsed map rows: **7** (7 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `blast-rivals-2026-season-1-natus-vincere-vs-vitality-bo5-Mv7s4IInKiHxzKeMZKCajF.rar`
  - `blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks.rar`
  - `blast-rivals-2026-season-1-vitality-vs-g2-bo3-QFGfmJ4pQ03xQPiA9-8d-X.rar`
  - `blast-rivals-2026-season-1-vitality-vs-gamerlegion-bo3-6uE9HTRZoNZoyLJ1b6CEsc.rar`

### `iem-atlanta-2026` — IEM Atlanta 2026

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **8**.
- Archives/series: **5**; parsed map rows: **8** (8 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `iem-atlanta-2026-b8-vs-vitality-bo3-nGRbmcCg2mU5uSsmD_vHGX.rar`
  - `iem-atlanta-2026-betboom-vs-vitality-bo3-RQMj4Ln9P780zqrqV8kusH.rar`
  - `iem-atlanta-2026-faze-vs-vitality-bo3-6Gd1Zicoah5akfYbegZ76d.rar`
  - `iem-atlanta-2026-natus-vincere-vs-vitality-bo3-Oy5NkCJPWmHl6H0cKtC9_L.rar`
  - `iem-atlanta-2026-vitality-vs-bcgame-bo3-vVbTCwcwhL6039kdua2CRF.rar`

### `iem-krakw-2026` — IEM Kraków 2026

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **8**.
- Archives/series: **5**; parsed map rows: **8** (8 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `iem-krakw-2026-3dmax-vs-vitality-bo3-wRh04OCAJb0TLZWmLhz1tg.rar`
  - `iem-krakw-2026-furia-vs-vitality-bo5-mm8dtsK9binWQO0i_PtQVF.rar`
  - `iem-krakw-2026-vitality-vs-aurora-bo3--mY74mcLmUrEjY-ofCuhG0.rar`
  - `iem-krakw-2026-vitality-vs-bcgame-bo3-1bS_vkLXGu0uvf773So7g-.rar`
  - `iem-krakw-2026-vitality-vs-mouz-bo3-UD0TEnJpRupm9E_EHc4hZG.rar`

### `iem-rio-2026` — IEM Rio 2026

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **9**.
- Archives/series: **6**; parsed map rows: **9** (9 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `iem-rio-2026-furia-vs-vitality-bo3--OutGDctKNBZKy28qkTgMB.rar`
  - `iem-rio-2026-spirit-vs-vitality-bo5-UR_LUBGmeXrZWQNI8kFJNV.rar`
  - `iem-rio-2026-vitality-vs-falcons-bo3-O2Ctrym3k5WQt8XytMQySq.rar`
  - `iem-rio-2026-vitality-vs-g2-bo3-yhOR34cA9Po02UrfKIOtO9.rar`
  - `iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r.rar`
  - `iem-rio-2026-vitality-vs-red-canids-bo3-59DoPvf6WpvmGfDT24G_S2.rar`

### `pgl-cluj-napoca-2026` — PGL Cluj-Napoca 2026

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **7**.
- Archives/series: **6**; parsed map rows: **7** (7 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `pgl-cluj-napoca-2026-mouz-vs-vitality-bo3-k_w5VQbpH9bZlYTAZc8SyE.rar`
  - `pgl-cluj-napoca-2026-parivision-vs-vitality-bo5-AmtSttVoC1qI4LHDRIW4S-.rar`
  - `pgl-cluj-napoca-2026-vitality-vs-aurora-bo3-Pn_Q-PJO50-mcoIjPX1Cjf.rar`
  - `pgl-cluj-napoca-2026-vitality-vs-g2-bo3-qYj9k9myd7QwvfmcK2ZjT5.rar`
  - `pgl-cluj-napoca-2026-vitality-vs-the-mongolz-bo3-HnIEEaHEW5z1jrP1O7fbaW.rar`
  - `pgl-cluj-napoca-2026-vitality-vs-the-mongolz-bo3-_V1-atgVjp_HiqnMb5rNMc.rar`

### `starladder-starseries-fall-2026` — StarLadder StarSeries Fall 2026

- Missing initially; **configured by the concurrent update**. Initial null-date map rows: **9**.
- Archives/series: **5**; parsed map rows: **9** (9 new); date null: **0**; ID-interpolated only: **0**.
- Series/archive counts with at least one parsed map: null dates **0**; ID-interpolated dates **0**.
- HLTV match IDs: **unavailable** (archive members have no numeric series IDs).
  - `starladder-starseries-fall-2026-aurora-vs-vitality-bo3-YKs8kEDNPDubjefvBPad28.rar`
  - `starladder-starseries-fall-2026-aurora-vs-vitality-bo5-a29hF-CpdWTocEVzwpQ_0F.rar`
  - `starladder-starseries-fall-2026-vitality-vs-furia-bo3-HgWry2z6SZbWx6OAju7RT-.rar`
  - `starladder-starseries-fall-2026-vitality-vs-furia-bo3-T02CXrqqgCdzggCxkdcv3r.rar`
  - `starladder-starseries-fall-2026-vitality-vs-magic-bo3-qBHOW2KPqxQBIay8cnoYpu.rar`

The Virtus.pro archive spells its team `virtuspro`, while members use `virtus-pro`. `playbook.dedupe.demo_event_slug` therefore returns null for that archive; its archive-derived event is grouped above, but export metadata has both `event` and `date` null for its accepted map. The alias file was left unchanged, and concurrent date edits were preserved.

Remaining undated active-pool Vitality map rows:

| Map | Demo ID | Opponent | HLTV match ID |
| --- | --- | --- | --- |
| de_mirage | hltv-de_mirage-2394170 | B8 | unavailable |
| de_dust2 | virtus-pro-vs-vitality-m2-dust2 | Virtus.pro_ | unavailable |

## Team names missing from the alias registry

Counts are appearances in newly parsed map rows, before content dedupe. Names may be valid new canonical names rather than misspellings; the lead should confirm the intended canonical form before adding aliases.

| Observed name | New map appearances | Source archives |
| --- | --- | --- |
| 100 Thieves | 1 | 1 |
| 1win | 2 | 1 |
| BC Game Esports | 3 | 2 |
| EYEBALLERS | 1 | 1 |
| FUT | 4 | 2 |
| FUT Esports | 1 | 1 |
| Inner Circle | 2 | 1 |
| PVISION | 2 | 1 |
| RED Canids | 1 | 1 |
| Virtus.pro_ | 1 | 1 |
| magic | 2 | 1 |

Clear spelling-merge candidates, supported by archive names and existing canonical names: `PVISION` → `PARIVISION`, `BC Game Esports` → `BC.Game`, `Virtus.pro_` → `Virtus.pro`; review `FUT` / `FUT Esports` together. Other rows may need new canonical entries. No aliases were edited.

See `_sync/gpt32/unknown-teams.json` for exact demo IDs and `_sync/gpt32/member-audit.json` for archive/member attribution.

## Import identity collisions

**18 demo identities occur in multiple downloaded archives.** `playbook.parse.demo_identity` uses the filename stem when no numeric HLTV ID is present; `scripts/import_hltv.py:_process` skips identities already seen before comparing match content. Different events can therefore be falsely treated as duplicate downloads. These are possible missing matches, not verified content duplicates.
Examples include `vitality-vs-falcons-m3-mirage` (BLAST Bounty Season 1 Finals vs ESL Pro League Season 24) and `mouz-vs-vitality-m1-dust2` (BLAST Open Porto vs PGL Cluj-Napoca). All 18 identities with exact source archives are in `_sync/gpt32/archive-identity-collisions.json`.
The existing pipeline was left unchanged as requested. The lead should resolve archive-scoped/series-scoped identity and reimport affected archives before claiming complete year coverage. Archives and skipped originals remain available.

## Content dedupe

- Export dropped **34** content duplicates in total (baseline **27**, net change **+7**).
- Strict HLTV/non-HLTV cross-source drops: **34**; remaining duplicate drops are within the same source category.
- Newly parsed rows dropped: **0**. Import filename/identity skips above are separate from content dedupe and are not added to this count.
- Exact kept/dropped IDs and maps: `_sync/gpt32/dedupe-after.json`; baseline: `_sync/gpt32/dedupe-before.json`.

## Archive-by-archive import results

I/D/O/F = imported games / duplicate identity skips / off-pool skips / failures. Duplicate checks precede map-pool checks. All original archives were retained. These are the 63 requested Vitality downloads; full importer results, including pre-existing Falcons archives, are in `_sync/gpt32/import-summary.json`.

| Archive | Maps in headers | I | D | O | F | Failure reason |
| --- | --- | --- | --- | --- | --- | --- |
| blast-bounty-2026-season-1-eyeballers-vs-vitality-bo3-cdixknqTHEiRBWJBE_PGSN.rar | de_anubis, de_overpass | 1 | 0 | 1 | 0 | — |
| blast-bounty-2026-season-1-finals-gamerlegion-vs-vitality-bo3-xvrJ9muhRij9eX0sOLSDM4.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-1-finals-vitality-vs-falcons-bo3-m75xkiVwc3YZkEbdtP1s9_.rar | de_anubis, de_inferno, de_mirage | 2 | 1 | 0 | 0 | — |
| blast-bounty-2026-season-1-virtuspro-vs-vitality-bo3-q1MsDOb5aD1l3u9zoYMQdQ.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| blast-bounty-2026-season-2-liquid-vs-vitality-bo3-qIJxv4f_-TgN3EMU0b5r8t.rar | de_anubis, de_nuke | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-furia-vs-vitality-bo3-KULcN3Jf23XthDsJCBq9hT.rar | de_cache, de_dust2, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-open-porto-2026-fut-vs-vitality-bo3-NtdD-eOTDdeUQsfjwK8sc4.rar | de_anubis, de_dust2 | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-mouz-vs-vitality-bo3-V3i93ufoKzBC0MBPii8PGf.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-vitality-vs-9z-bo3-p-u8ZqQpw4ORQzAjpnwJBy.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-vitality-vs-inner-circle-bo3-MHhZuz8xuP_ejiwRkgvSY2.rar | de_anubis, de_cache | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-vitality-vs-legacy-bo3-Pu1xg3di2XCxKNuhUGwTec.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-parivision-vs-vitality-bo3-hiwqXfBGRevcYWe8xgLMbB.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-the-mongolz-vs-vitality-bo3-7AUu3EcXrnLd4gicqzNp8L.rar | de_mirage, de_overpass | 1 | 0 | 1 | 0 | — |
| blast-open-rotterdam-2026-vitality-vs-9z-bo3-kVsrbfS7P7ANQA8A6NP-eu.rar | de_nuke, de_overpass | 0 | 1 | 1 | 0 | — |
| blast-open-rotterdam-2026-vitality-vs-aurora-bo3-FlxFvdx4Pl-M44Zsyy4BH3.rar | de_inferno, de_nuke | 2 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-vitality-vs-natus-vincere-bo5-M1X_ekEYL-WVFzIqhTKs9U.rar | de_anubis, de_dust2, de_inferno | 3 | 0 | 0 | 0 | — |
| blast-rivals-2026-season-1-natus-vincere-vs-vitality-bo5-Mv7s4IInKiHxzKeMZKCajF.rar | de_anubis, de_dust2, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-rivals-2026-season-1-vitality-vs-g2-bo3-QFGfmJ4pQ03xQPiA9-8d-X.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| blast-rivals-2026-season-1-vitality-vs-gamerlegion-bo3-6uE9HTRZoNZoyLJ1b6CEsc.rar | de_mirage, de_overpass | 1 | 0 | 1 | 0 | — |
| esl-pro-league-season-24-aurora-vs-vitality-bo3-jz97l79s_ZddmLmtUQ37rg.rar | de_anubis, de_cache, de_mirage | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-vitality-vs-1win-bo3-IMbwm15qZnZZ6EZYeQXExQ.rar | de_cache, de_dust2 | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-vitality-vs-falcons-bo3-tjOq40YPwMI3QHOotPr9e9.rar | de_anubis, de_dust2, de_mirage | 0 | 3 | 0 | 0 | — |
| esl-pro-league-season-24-vitality-vs-mouz-bo5-HHVdkDbJrwRclevPphxD2-.rar | de_cache, de_dust2, de_inferno | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-vitality-vs-natus-vincere-bo3-rAyrt8Fnq-0Skx1b2XM0hC.rar | de_anubis, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-vitality-vs-parivision-bo3-UFS87rZoI0SoWeaKEAEusH.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-b8-vs-vitality-bo3-N4CDgIbMarl-Be8034f4a_.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-faze-vs-vitality-bo3-62SRZyouxVyNwwo1JtPLmM.rar | de_cache, de_dust2 | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-lynn-vision-vs-vitality-bo3-LW8QjJ062PMCxTmNJ2gWJQ.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-vitality-vs-100-thieves-nuke-xgmnZlKoCUg1rSdM6g5Q-g.rar | de_nuke | 1 | 0 | 0 | 0 | — |
| esports-world-cup-2026-vitality-vs-spirit-bo3-feerxWVU296AZ9J8Dbc9si.rar | de_anubis, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| iem-atlanta-2026-b8-vs-vitality-bo3-nGRbmcCg2mU5uSsmD_vHGX.rar | de_dust2, de_mirage | 1 | 1 | 0 | 0 | — |
| iem-atlanta-2026-betboom-vs-vitality-bo3-RQMj4Ln9P780zqrqV8kusH.rar | de_anubis, de_nuke, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-atlanta-2026-faze-vs-vitality-bo3-6Gd1Zicoah5akfYbegZ76d.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| iem-atlanta-2026-natus-vincere-vs-vitality-bo3-Oy5NkCJPWmHl6H0cKtC9_L.rar | de_anubis, de_dust2, de_inferno | 2 | 1 | 0 | 0 | — |
| iem-atlanta-2026-vitality-vs-bcgame-bo3-vVbTCwcwhL6039kdua2CRF.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-betboom-vs-vitality-bo3-XBvPIFP-w6HGsMHgX5Tjhh.rar | de_nuke, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-cologne-major-2026-falcons-vs-vitality-bo3-Q3edu52gPDbzXK7dImpXFr.rar | de_anubis, de_dust2, de_inferno | 0 | 3 | 0 | 0 | — |
| iem-cologne-major-2026-vitality-vs-9z-bo3-g80npa9dndYlfdx7MCyRLz.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-vitality-vs-fut-bo3-rNsUTmTOO26ftPbfiPVp79.rar | de_anubis, de_nuke, de_overpass | 1 | 1 | 1 | 0 | — |
| iem-cologne-major-2026-vitality-vs-mouz-bo3-E9khg_TX6BxGaIZNKJ3X1O.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| iem-krakw-2026-3dmax-vs-vitality-bo3-wRh04OCAJb0TLZWmLhz1tg.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-furia-vs-vitality-bo5-mm8dtsK9binWQO0i_PtQVF.rar | de_inferno, de_mirage, de_nuke, de_overpass | 3 | 0 | 1 | 0 | — |
| iem-krakw-2026-vitality-vs-aurora-bo3--mY74mcLmUrEjY-ofCuhG0.rar | de_ancient, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-krakw-2026-vitality-vs-bcgame-bo3-1bS_vkLXGu0uvf773So7g-.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-krakw-2026-vitality-vs-mouz-bo3-UD0TEnJpRupm9E_EHc4hZG.rar | de_dust2, de_nuke | 1 | 1 | 0 | 0 | — |
| iem-rio-2026-furia-vs-vitality-bo3--OutGDctKNBZKy28qkTgMB.rar | de_ancient, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-rio-2026-spirit-vs-vitality-bo5-UR_LUBGmeXrZWQNI8kFJNV.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| iem-rio-2026-vitality-vs-falcons-bo3-O2Ctrym3k5WQt8XytMQySq.rar | de_dust2, de_mirage, de_nuke | 2 | 1 | 0 | 0 | — |
| iem-rio-2026-vitality-vs-g2-bo3-yhOR34cA9Po02UrfKIOtO9.rar | de_dust2, de_inferno, de_mirage | 1 | 2 | 0 | 0 | — |
| iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-vitality-vs-red-canids-bo3-59DoPvf6WpvmGfDT24G_S2.rar | de_nuke, de_overpass | 1 | 0 | 1 | 0 | — |
| pgl-cluj-napoca-2026-mouz-vs-vitality-bo3-k_w5VQbpH9bZlYTAZc8SyE.rar | de_dust2, de_inferno | 1 | 1 | 0 | 0 | — |
| pgl-cluj-napoca-2026-parivision-vs-vitality-bo5-AmtSttVoC1qI4LHDRIW4S-.rar | de_dust2, de_inferno, de_overpass | 2 | 0 | 1 | 0 | — |
| pgl-cluj-napoca-2026-vitality-vs-aurora-bo3-Pn_Q-PJO50-mcoIjPX1Cjf.rar | de_inferno, de_overpass | 0 | 1 | 1 | 0 | — |
| pgl-cluj-napoca-2026-vitality-vs-g2-bo3-qYj9k9myd7QwvfmcK2ZjT5.rar | de_anubis, de_inferno, de_mirage | 1 | 2 | 0 | 0 | — |
| pgl-cluj-napoca-2026-vitality-vs-the-mongolz-bo3-HnIEEaHEW5z1jrP1O7fbaW.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-vitality-vs-the-mongolz-bo3-_V1-atgVjp_HiqnMb5rNMc.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | — |
| starladder-starseries-fall-2026-aurora-vs-vitality-bo3-YKs8kEDNPDubjefvBPad28.rar | de_anubis, de_inferno, de_nuke | 2 | 1 | 0 | 0 | — |
| starladder-starseries-fall-2026-aurora-vs-vitality-bo5-a29hF-CpdWTocEVzwpQ_0F.rar | de_anubis, de_cache, de_inferno, de_mirage | 1 | 3 | 0 | 0 | — |
| starladder-starseries-fall-2026-vitality-vs-furia-bo3-HgWry2z6SZbWx6OAju7RT-.rar | de_anubis, de_cache | 2 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-vitality-vs-furia-bo3-T02CXrqqgCdzggCxkdcv3r.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-vitality-vs-magic-bo3-qBHOW2KPqxQBIay8cnoYpu.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |

## Broken demos and parse result

Complete parse output: `_sync/gpt32/parse-full.log` (captured before `refresh.sh` truncates it with `tail -3`).

```text
[444/444] hltv-de_mirage-2394170.dem
  hltv-de_mirage-2394170: de_mirage B8 5-13 Vitality | 18 rounds, 123 kills, 7 plants, 319 grenades (5 without thrower) | 5.5s
done: 423 ok, 21 failed -> /Users/stephen/Downloads/cs2-pro-playbook/data/parsed
```

**21** game groups failed validation: **7 newly imported**, **14 pre-existing**. No failed game stopped unrelated parsing or export. Exact paths and reasons are also in `_sync/gpt32/parse-failures.json`.

| Demo/progress entry | Reason |
| --- | --- |
| data/raw/cs2povarchive/cac2026/2394225-falcons-vs-mouz/falcons-vs-mouz-m3-nuke.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p2.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p3.dem | ValueError: Part 2: round has no recognized winner |
| data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| data/raw/cs2povarchive/iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m2-dust2-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m2-dust2-p2.dem | ValueError: Incomplete rounds have no complete copy: [13] |
| data/raw/hltv/blast-bounty-2026-season-2-100-thieves-vs-falcons-bo3-1e-d96xDiJ9l7gcqrB38LA/100-thieves-vs-falcons-m3-anubis.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-open-porto-2026-falcons-vs-lynn-vision-bo3-IdZAgRUbsqRX4U5Llhxy2P/falcons-vs-lynn-vision-m3-dust2.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-open-porto-2026-furia-vs-vitality-bo3-KULcN3Jf23XthDsJCBq9hT/furia-vs-vitality-m3-dust2.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-open-porto-2026-legacy-vs-falcons-bo3-gq5W-Wo-iXLjtfndNgImik/legacy-vs-falcons-m3-dust2.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-open-porto-2026-mouz-vs-falcons-bo3-prw6BqDfxCxFQUiDy4b4ey/mouz-vs-falcons-m3-inferno.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-open-porto-2026-vitality-vs-legacy-bo3-Pu1xg3di2XCxKNuhUGwTec/vitality-vs-legacy-m3-dust2.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks/vitality-vs-fut-m3-nuke.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/blast-rivals-2026-season-1-vitality-vs-g2-bo3-QFGfmJ4pQ03xQPiA9-8d-X/vitality-vs-g2-m3-dust2.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/cs-asia-championships-2026-falcons-vs-mouz-bo3--bPrjLQ2TP-mMaeM2Zy1DS/falcons-vs-mouz-m3-nuke.dem | ValueError: Invalid or overlapping round bounds; possible backup restore |
| data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| data/raw/hltv/iem-atlanta-2026-faze-vs-vitality-bo3-6Gd1Zicoah5akfYbegZ76d/faze-vs-vitality-m1-nuke-p1.dem + data/raw/hltv/iem-atlanta-2026-faze-vs-vitality-bo3-6Gd1Zicoah5akfYbegZ76d/faze-vs-vitality-m1-nuke-p2.dem | ValueError: Part 2: round has no recognized winner |
| data/raw/hltv/iem-cologne-major-2026-vitality-vs-mouz-bo3-E9khg_TX6BxGaIZNKJ3X1O/vitality-vs-mouz-m2-dust2-p1.dem + data/raw/hltv/iem-cologne-major-2026-vitality-vs-mouz-bo3-E9khg_TX6BxGaIZNKJ3X1O/vitality-vs-mouz-m2-dust2-p2.dem | ValueError: Incomplete rounds have no complete copy: [13] |
| data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p1.dem + data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |

## Preview and tests

- `cp -R data/site/. site-preview/data/`: exit 0; 1.223s wall time.
- SHA-256 verification: 2941 exported files checked; 0 mismatches; 0.732s wall time.
- `.venv/bin/python -m pytest -q`: exit 0; 19.256s wall time.
- Pytest result: `256 passed, 3 skipped, 1 warning in 19.02s`. Full output: `_sync/gpt32/pytest.log`.
- Final date consistency check: 766 exported team-profile match entries compared with current `config/events.json` resolution; 0 mismatches.

## Immediate follow-up

- Review the schedules supplied by the concurrent `config/events.json` update (including the noted approximate online start); no archive-derived event slugs remain missing. Add exact dates/series IDs only from authoritative match records.
- Resolve the cross-archive filename identity collisions before a completeness claim; then reimport the preserved archives.
- Review the unknown team spellings above and the Virtus.pro archive/event spelling mismatch.
- Add verified Cache map/radar metadata before relying on the newly exported Cache tactical or position views.
- Review broken demos listed above; successful games continued through export.
- Regenerate team commentary where facts changed: export invalidates old fact fingerprints; `refresh.sh` refreshed the commentary inputs.
