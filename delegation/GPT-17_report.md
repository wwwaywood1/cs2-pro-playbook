# GPT-17 round-two report

Implementation complete in place. Scope: desktop Chinese UI. All 29 new translation keys exactly match `delegation/inputs/copy_round2.json`; English temporarily uses the same Chinese copy. No raw data, images, `.github`, or `delegation/design-skills/` edited. No Git metadata is present in this checkout.

## Baseline, run before implementation
- `.venv/bin/python -m playbook export`: **passed**.
- `.venv/bin/python -m pytest -q`: **185 passed, 1 skipped**, 30.74 s.

## Requested items
1. **Done — Player heatmap.** `web/src/pages/TeamsHub.tsx` defaults to T; old `side=all` player links canonicalize to T. Both it and `web/src/pages/TeamHeatmap.tsx` expose 开局 / 中期控图 / 下包后/残局 with the supplied caption and actual phase grids. Utility heatmaps also respect the selected phase; detailed utility lists retain their existing full-side scope.
2. **Done — WPA.** `web/src/components/PlayerWpa.tsx` headlines exported extra rounds per match and top-percentile placement. Exported percentile is the fraction at/below the player, so UI top percentage is its complement (minimum top 1%). Null percentile shows the supplied small-sample text. Duel contribution stays small; utility contribution is hidden; tooltip uses the supplied copy.
3. **Done — Team round chart and metadata.** `web/src/components/MatchWinprob.tsx` draws one green/red delta bar per round, a divider after round 12, and supplied start/end tooltip. `playbook/export.py:team_round_sides` exports actual team sides, including overtime, rather than inferring halves. Match availability flags prevent requests for absent timelines; older timelines without side metadata are hidden. `web/src/pages/Team.tsx` shows available event/date and omits missing metadata.
4. **Done — Lineup radar.** `web/src/components/Radar.tsx` replaces grid clustering with one callout/place marker at coordinate medians of the exported landing representatives. Marker size and displayed count use summed throws. Clicking expands only that place; hovered/selected cards reveal their route; the reset collapses the overview. Filters reset expansion.
5. **Done — Lineup teaching details.** `web/src/pages/Lineups.tsx` uses the supplied pop-time/help copy, all/≥10/≥50 tiers and technique labels. Active radar routes show throw position and a short yaw arrow with supplied help. `build_lineups` already exported technique and `throw.yaw`; a regression test now verifies both against source throws.
6. **Done — Recipe assignments.** `playbook/tactics.py:execute_recipes` adds `thrower` and `order` to core/option SpotRefs. Uses only the recipe rounds, matching T team, and eligible execution-window throws. Names use a deterministic mode; order ranks median pop times with stable ties. `web/src/pages/Tactics.tsx` shows both annotations and the supplied match count. All 464 exported SpotRefs have both fields.
7. **Done — Home cards.** `playbook/export.py:map_card_summary` adds round-weighted T/CT win rates and the most-used recipe to the index. `web/src/pages/Home.tsx` replaces card database totals with those values; Cache has the supplied no-data state and no empty counts.
8. **Done — Team slide.** `web/src/teams-hub.css` constrains the desktop logo/header block to 15svh, capped at 22svh. Map rings use strong green at ≥65%, neutral from 48% to <65%, muted red below 48%; best/worst maps have supplied badges. Hover preserves the semantic ring colour. Rankings exclude unknown rates; a sole known map receives only the best badge.
9. **Done — Sample hierarchy.** Player gun-round sample count is small metadata beside the title; three main stat cards remain.
10. **Done — Entrance compromise.** First full and repeat short session entrances and verse remain. Skip uses compact supplied copy. Verse characters fade/blur as whole glyphs; `web/src/components/CountUp.tsx` reveals complete final numbers without rolling tracks or clipping masks. Reduced-motion and interruption behavior are retained.
11. **Done — Colour semantics.** `web/src/theme.ts` now exports dedicated team-brand tokens, used for logo/portrait lighting. Navigation has one green brand colour. T data stays amber, CT blue, including side-specific ownership shades on the detailed heatmap. Positive WPA is green; negative WPA is dark red.

## Final verification
- `.venv/bin/python -m playbook export`: **passed, exit 0** after the final backend change. Log: `delegation/GPT-17_export.log`.
- `.venv/bin/python -m pytest -q`: **190 passed, 1 skipped, 1 warning**, 28.88 s. Log: `delegation/GPT-17_pytest.log`. The skipped test requires Node with native TypeScript support (`tests/test_review02.py:304`); the warning is joblib falling back from physical to logical core detection.
- Targeted data regression run: **41 passed, 1 skipped**; final narrow export/metadata run: **6 passed**. New coverage is in `tests/test_review_round2.py`.
- Export integrity checked: **6 active maps, 283 map matches, 13,014 lineups, 99 recipes, 464 complete and uniquely ordered SpotRefs, 85 team-relative timelines and 170 match rows referencing available charts**. Every referenced timeline covers its team's recorded sides; map rates sum to 100%; top recipes resolve.
- Model summary: 27 duplicate demos removed; 289 model matches (includes maps outside the displayed active pool), accuracy **0.743** vs **0.697** baseline, log loss **0.471**.
- Matches / lineups: Ancient **43 / 2177**, Anubis **24 / 1417**, Dust II **63 / 3014**, Inferno **47 / 2173**, Mirage **57 / 2443**, Nuke **49 / 1790**.
- Synced **532 generated JSON files** from `data/site/` into `web/public/data/` without copying images.
- Python compilation passed for changed backend/test/smoke files. Translation audit found no missing constant lookup keys; named imports/types reviewed in source.

## Partial validation / next check
**Partial — frontend execution only.** Node/npm/tsc are absent, as stated in the task; Python Playwright is also absent. No frontend build, browser smoke execution or screenshot QA was possible, and the existing `web/dist` was not treated as a build of these edits. `web/e2e/smoke.py` has been updated for usage tiers, callout expansion, yaw direction, T defaults/back navigation, phase controls, Cache state, three KPIs and the inline sample count.

On a machine with frontend tooling, run `npm ci && npm run build` in `web/`, then run the documented sample-data browser smoke workflow in `web/e2e/smoke.py`. Preserve the generated production JSON before switching to sample fixtures. Review the desktop player entrance, callout drilldown and team-relative bars visually.
