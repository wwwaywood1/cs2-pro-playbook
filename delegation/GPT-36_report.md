# GPT-36 Spirit ingest report

## Result

- Status: **exported and preview synchronized**.
- Found **58 Spirit archives**, **39,504,388,125 bytes**; archive listing failures: **0**.
- Actual archive moves: **52**; existing same-name destinations preserved: **6**. Downloaded copies of existing archives were left in place; original archived data was retained. See `_sync/gpt36/existing-archive-copies.json` for SHA-256 comparisons.
- **2 unrelated HLTV downloads** left untouched. Exact paths: `_sync/gpt36/excluded-downloads.json`.
- Selected archive totals (games, not archive files): **115 imported**, **15 duplicate skips**, **10 off-pool skips**, **0 import failures**. Archives contributing imports: **53**; no new imports: **5**.
- Newly parsed rows across the full refresh: **117**; Spirit rows: **112**. New rows retained by content dedupe: **117**; from the selected archives: **112**.
- The full refresh also imported **5** games from **4** pre-existing non-selected archives. Exact importer rows are retained in `_sync/gpt36/import-summary.json`; these are separate from the Spirit archive totals.
- Ran `bash scripts/refresh.sh` using `_sync/gpt36/instrument.bash` via `BASH_ENV` for scoped moves, full parse logs, stage timings, and a pre-export event gate. Production scripts and Python source were not edited.
- Source/config hash differences since baseline: **config/events.json**. Any concurrent changes were preserved; this ingest agent did not invent or edit event dates.

## Stage wall times

```text
PREPARE elapsed=0.620 archives=58 excluded=2
SHELL_START 0
MOVE elapsed=0
START 0 scripts/import_hltv.py
END 2287 elapsed=2287 rc=0 scripts/import_hltv.py
START 2287 -m playbook parse
END 5044 elapsed=2757 rc=1 -m playbook parse
START 5044 -m playbook export
END 5933 elapsed=889 rc=0 -m playbook export
START 5933 scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
END 5933 elapsed=0 rc=0 scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
COPY elapsed=1.342 rc=0
PYTEST elapsed=20.375 rc=0
```

## Missing event schedules

All downloaded archive event slugs have configured schedules at the final check. No event dates were fabricated.

The following schedules were missing initially and were supplied by an external configuration update before export; this agent preserved the update. The ten-minute wait was unnecessary because all schedules were present when the export gate ran. Original archive/member attribution is preserved in `delegation/GPT-36_missing_events.txt` and `_sync/gpt36/missing-events-at-initial-inspection.json`.

- `blast-bounty-2026-season-2-finals`
- `esl-pro-league-season-23-finals`
- `esl-pro-league-season-23-stage-2`
- `iem-cologne-major-2026-stage-2`

## Spirit maps before → after

Counts below read `data/site/<map>/teams.json`; the staged column independently counts parsed tables after content dedupe. Overpass is historical and outside `ACTIVE_POOL`.

| Map | Published before | Published after | Staged after dedupe |
| --- | --- | --- | --- |
| de_ancient | 2 | 19 | 19 |
| de_anubis | 5 | 16 | 16 |
| de_cache | 0 | 8 | 8 |
| de_dust2 | 7 | 40 | 40 |
| de_inferno | 0 | 0 | 0 |
| de_mirage | 9 | 31 | 31 |
| de_nuke | 5 | 15 | 15 |
| de_overpass | 2 | 2 | outside pool |

Active-pool published total: **28 → 129**. Staged active-pool Spirit maps: **129**.

## Date precision

- Published active-pool dated coverage: **2026-01-12 → 2026-10-03** (configured event starts / estimated days / exact overrides as labeled below).
- Published active-pool export: `{'exact': 0, 'day': 2, 'event': 127, 'null': 0}`.
- Staged Spirit active-pool map rows after dedupe: `{'exact': 0, 'day': 2, 'event': 127, 'null': 0}`.
- Newly parsed Spirit rows before dedupe: `{'exact': 0, 'day': 0, 'event': 112, 'null': 0}`.
`event` = configured event start; `day` = estimated HLTV-ID rank interpolation, not exact match day; `exact` = explicit CSV override; `null` = unresolved.

## Team names and aliases

Counts are appearances in newly parsed map rows before content dedupe. Unknown names may be valid new teams; no new canonical identities were guessed.

| Observed name | New map appearances | Proposed action |
| --- | --- | --- |
| 100T | 3 | 100T → 100 Thieves (new canonical candidate; lead review, not added) |
| 1win | 2 | 1win → 1win (new canonical candidate; lead review, not added) |
| Inner Circle Esports | 2 | Inner Circle Esports → Inner Circle (new canonical candidate; lead review, not added) |
| Luminosity | 1 | Luminosity → Luminosity (new canonical candidate; lead review, not added) |
| OG CS2 | 3 | OG CS2 → OG (new canonical candidate; lead review, not added) |
| RED Canids | 2 | RED Canids → RED Canids (new canonical candidate; lead review, not added) |
| SINNERS ESPORT | 2 | SINNERS ESPORT → SINNERS (new canonical candidate; lead review, not added) |
| ShindeN | 3 | ShindeN → ShindeN (new canonical candidate; lead review, not added) |
| The Huns | 2 | The Huns → The Huns (new canonical candidate; lead review, not added) |

Exact demo IDs: `_sync/gpt36/unknown-teams.json`. No obvious spelling variants of existing canonical names were found, so no alias rows were added. Audit: `_sync/gpt36/alias-audit.json`; changes: `_sync/gpt36/alias-changes.json`.

## Content dedupe

- Total parsed content duplicates: **52**; baseline **38**; net change **+14**.
- Strict HLTV versus non-HLTV cross-source duplicates: **52**.
- Newly parsed rows dropped: **0**. All new parsed rows were retained; duplicate removal affected pre-existing recordings.
- Import identity skips above are separate from content dedupe. Exact retained/dropped IDs: `_sync/gpt36/dedupe-after.json`.

## Archive-by-archive import results

I / D / O / F = imported games / duplicate identity skips / off-pool skips / failures. Header maps are listed before filtering. Duplicate checks precede pool checks.

| Archive | Header maps | I | D | O | F | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| blast-bounty-2026-season-1-finals-parivision-vs-spirit-bo3-CpEROJyXP8nd1x7BTCyu61.rar | de_ancient, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| blast-bounty-2026-season-1-inner-circle-vs-spirit-bo3-MfhEGJq5Wo_xqc_g50_1iQ.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-1-sinners-vs-spirit-bo3-cTn_H9juISZmERJ0ZmI2l0.rar | de_mirage, de_nuke | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-100-thieves-vs-spirit-bo3-jczcENf0aTGcvNESAsG5ib.rar | de_anubis, de_dust2, de_mirage | 3 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-finals-faze-vs-spirit-bo3-9h2onDXX3gz_Ctzlsgfhnk.rar | de_anubis, de_cache, de_dust2 | 3 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-finals-liquid-vs-spirit-bo3-umEnlvr6xG9WlWGrp-nFPU.rar | de_anubis, de_dust2 | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-finals-spirit-vs-mouz-bo5--wn1awkp4iFRmswi58ug57.rar | de_ancient, de_dust2, de_mirage, de_nuke | 4 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-og-vs-spirit-bo3-P0hojm_LpZWAZatlwoC6xJ.rar | de_ancient, de_cache, de_dust2 | 3 | 0 | 0 | 0 | — |
| blast-open-porto-2026-g2-vs-spirit-bo3-zmCjt87Rl5n3ZHaNGybjtx.rar | de_cache, de_dust2 | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-spirit-vs-dendele-bo3-GRiQxm5iEKnKGeOn4zbdbQ.rar | de_ancient, de_cache | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-spirit-vs-falcons-bo3-fzVRj3juYH_FTkHv4edkex.rar | de_ancient, de_nuke | 0 | 2 | 0 | 0 | duplicate identity |
| blast-open-porto-2026-spirit-vs-furia-bo3-DLIuxJDviZLxHemrpqI9i8.rar | de_ancient, de_cache | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-spirit-vs-mouz-bo5-sZmuJNNeP4vy0G6o8VuS_u.rar | de_ancient, de_dust2, de_mirage, de_nuke | 4 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-9z-vs-spirit-bo3-lnFGG3HaAlznJFLz1Iw0h2.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| blast-open-rotterdam-2026-parivision-vs-spirit-bo3-BM5oinQU0VRWoyAifSAcom.rar | de_ancient, de_anubis | 2 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-spirit-vs-liquid-bo3-KQP2H3l3wjdOpSXxWAH3rw.rar | de_ancient, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-the-mongolz-vs-spirit-bo3-sZcq7b-2moO4gI_-zfbR6P.rar | de_nuke, de_overpass | 1 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-finals-astralis-vs-spirit-bo3-0wMle9ouh2c-oVXVQBD8k_.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-23-stage-2-spirit-vs-3dmax-bo3-UG28lYiaKLCGNZcwg7-kFU.rar | de_nuke, de_overpass | 1 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q.rar | de_anubis, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-23-stage-2-spirit-vs-g2-bo3-Bi1MyOFl2RGc5zvtV7JFFo.rar | de_ancient, de_anubis | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-aurora-vs-spirit-bo3-Xy401Fit7Af8A-tXKiDV6u.rar | de_anubis, de_mirage | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-falcons-vs-spirit-bo3-7qoiS3mfVYinuAhEY9FtFF.rar | de_anubis, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| esl-pro-league-season-24-mouz-vs-spirit-bo3-sqctTxs0ADRlg-g18Xysab.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-spirit-vs-1win-bo3-F5n5BX2iZgXHqvm6sCMkvp.rar | de_anubis, de_cache | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-spirit-vs-m80-bo3-CGfM7ImIB2PanV5w6FKzdI.rar | de_cache, de_dust2 | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-spirit-vs-mouz-bo3-1EAS0FkXk363N7dvfZunnl.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-spirit-vs-parivision-bo3-I1FyZ9C4Y1Df9adH_HJUNq.rar | de_ancient, de_anubis, de_dust2 | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-spirit-vs-shinden-bo3-46eoTx2T5H7O5i_PicsmWL.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-b8-vs-spirit-bo3-P1Vazh1tOeViaVRokCR5Du.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-legacy-vs-spirit-bo3-2pu8CugYirqkV-rvX3j09c.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-spirit-vs-big-bo3-sbLMr0RufzMZ16gErFoh4R.rar | de_cache, de_dust2, de_mirage | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-vitality-vs-spirit-bo3-feerxWVU296AZ9J8Dbc9si.rar | de_anubis, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP.rar | de_anubis, de_dust2, de_nuke | 3 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-g2-vs-spirit-bo3-47sPOFVPbC3W0qqMbD_6GI.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-cologne-major-2026-natus-vincere-vs-spirit-bo3-kgjfQml_20SbX4SdXD-5FD.rar | de_anubis, de_dust2 | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-spirit-vs-9z-bo3-45Pa-VT_LG_Y7YLMszV2ng.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-cologne-major-2026-spirit-vs-falcons-bo3-wEPPcZigNVs8eZdF9kjqcz.rar | de_anubis, de_dust2, de_mirage | 0 | 3 | 0 | 0 | duplicate identity |
| iem-cologne-major-2026-stage-2-spirit-vs-9z-bo3-9Jsb2c3P-770y3kHwW6S1L.rar | de_mirage, de_nuke | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-g2-vs-spirit-bo3-lvH8ANpVzTw8QdVl0TEJzT.rar | de_anubis, de_dust2, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-krakw-2026-natus-vincere-vs-spirit-bo3-nWhIOX_dYygcuq3B3ZOrsF.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-spirit-vs-astralis-bo3-qoyf4tbtOCZaGnut4o9qFv.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-krakw-2026-spirit-vs-furia-bo3-xg2IF7BkV4uvqIFjZDhn6_.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| iem-krakw-2026-spirit-vs-mouz-bo3-CEc0ZCsgWfgqi6LSlIvIKf.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-falcons-vs-spirit-bo3-t9iYeYNZuxit-v9wZ84Lp_.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-g2-vs-spirit-bo3-3yEsHKCo6x0q-NMccrjUtt.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-red-canids-vs-spirit-bo3-8R5J8BuQk8V3vSkqD1TKqz.rar | de_ancient, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-rio-2026-spirit-vs-falcons-bo3-j0UWf3UXc8M1a3aXHV-7Eh.rar | de_anubis, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-spirit-vs-mouz-bo3-LLeNrfxqmFATTTqxsNE47B.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-spirit-vs-vitality-bo5-UR_LUBGmeXrZWQNI8kFJNV.rar | de_dust2, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| pgl-astana-2026-furia-vs-spirit-bo3-EOF1N3EPnLVYSd7SJXSkzP.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| pgl-astana-2026-mouz-vs-spirit-bo3-_ww1ZOkFS016IKZt45YjUx.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-spirit-vs-falcons-bo5-TrXwT8oW78oW7cKgmPrDgU.rar | de_ancient, de_dust2, de_mirage | 1 | 2 | 0 | 0 | — |
| pgl-astana-2026-spirit-vs-g2-bo3-btCis9NhL78367yEMKeFBV.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-spirit-vs-the-huns-bo3-SCqTAf-OVDFsZQZ0btfUej.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-the-mongolz-vs-spirit-bo3-XzNa-PUQkEyodLHmKoU2-f.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |

## Parse failures

**11 failures**: **3 newly imported**, **8 pre-existing**. Broken games did not stop unrelated parsing. Full traceback log: `_sync/gpt36/parse-full.log`; structured errors: `_sync/gpt36/parse-failures.json`.

| Scope | Demo path | Parse error |
| --- | --- | --- |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p2.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p3.dem | ValueError: Incomplete rounds have no complete copy: [1] |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| newly imported | data/raw/hltv/esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q/spirit-vs-b8-m1-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q/spirit-vs-b8-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| newly imported | data/raw/hltv/esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB/luminosity-vs-spirit-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB/luminosity-vs-spirit-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| newly imported | data/raw/hltv/iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs/spirit-vs-liquid-m1-ancient-p1.dem + data/raw/hltv/iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs/spirit-vs-liquid-m1-ancient-p2.dem | ValueError: Part 2: round has no recognized winner |
| pre-existing | data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p1.dem + data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |

```text
[582/583] falcons-vs-ninjas-in-pyjamas-m2-dust2: already parsed, skipping
[583/583] hltv-de_mirage-2394170: already parsed, skipping
done: 572 ok, 11 failed -> /Users/stephen/Downloads/cs2-pro-playbook/data/parsed
```

## Spirit roster from the export

Source: `data/site/heatmap_teams.json`, Spirit `roster` (name → Steam ID, aggregate rounds over deduplicated parsed data, including retained historical maps). This is the newly refreshed export.

| Name | Steam ID | Rounds |
| --- | --- | --- |
| magixx | 76561199063238565 | 2840 |
| sh1ro | 76561198081484775 | 2840 |
| tN1R | 76561198872013168 | 2840 |
| zont1x | 76561198995880877 | 2840 |
| donk | 76561198386265483 | 2781 |
| donk | 76561198018303780 | 59 |


**Roster identity split:** `donk` appears under `76561198386265483` (2,781 rounds) and `76561198018303780` (59 rounds). The latter occurs on IEM Rio Spirit–Liquid Dust2 (24 rounds), Spirit–Falcons Anubis (17), and Spirit–Falcons Mirage (18). These are exported source identities; no player-ID merge was made. Verify whether the secondary ID is an alternate account or a labeling issue before consolidating profiles. Exact demo IDs and raw paths: `_sync/gpt36/roster-identity-anomaly.json`.

## Preview and tests

- Preview copy: completed. Checked 3513 files; mismatches: 0.
- `.venv/bin/python -m pytest -q`: exit **0**, **20.375s**; `274 passed, 3 skipped, 1 warning in 20.06s`. Full log: `_sync/gpt36/pytest.log`.

## Immediate next steps

- Review the two Steam IDs exported as `donk` using the three source maps above; keep them separate until verified.
- Review unknown opponent names and re-download/review the three broken Spirit games listed above.
- `config/maps/de_cache.toml` is absent; staged Cache demos use fallback map metadata. Verify map/radar metadata before relying on Cache tactical or position views.
