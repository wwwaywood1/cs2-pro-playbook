# GPT-20 QA sweep report

Completed in `/Users/stephen/Downloads/cs2-pro-playbook` on 2026-10-22. Scope: desktop Chinese UI; locale cleanup also keeps English aligned. No npm dependencies added. `playbook/`, data, images, `.github/`, and `delegation/design-skills/` were not edited.

## Replay fixes

- `web/src/components/RoundReplay.tsx`: keep `ReplayModal` mounted while changing rounds; key `ReplayContent` by map/demo/round. Each switch discards old viewer state, cancels its RAF/listeners/ResizeObserver, and starts at 0 seconds and 1× speed. Existing `useData` active-request cleanup already ignores late responses; retaining that guard avoids aborting shared cached requests.
- Playback RAF uses functional time updates and restarts on speed changes; its existing cleanup cancels the pending frame on pause/unmount. No replay timers exist. Keyboard handlers use current time and functional play/seek updates: Space toggles playback, ←/→ seek exactly one second with bounds and pause, Esc closes.
- Native modal dialog plus explicit Tab/Shift+Tab wrapping contains focus. Round switches recover focus when the focused player disappears. Closing restores the connected original opener; the modal lifetime preserves the original body overflow value and its inline priority.
- Reduced-motion preference prevents initial autoplay and pauses playback if enabled later. Deliberate Play/Space remains available.
- `web/src/replay.css`: square radar fills `min(70vh, available modal content width)`; modal width follows that size. ResizeObserver keeps player dots at 9 CSS px diameter with a 1 px dark non-scaling outline. Only hovered/focused or selected living players receive visible names. Selection uses click/Enter.
- Preserve win-probability sample indices when filtering invalid samples, so later points retain their actual timestamps.

## Cleanup totals

- Translation keys: **76 removed from each locale (152 entries total)**; 486 leaf keys remain in each. No referenced Chinese keys were missing. Literal keys, runtime enum domains, locale key parity and interpolation placeholder parity were checked. Runtime map callouts remain because `calloutLabel(map, name)` resolves data-driven names.
- CSS: **26 selector branches removed**, covering **12 unused class names**. Shared rules retain their live branches. Dynamic grenade/arrow/badge/chip/side/outcome/effect classes remain.
- Components/exports: removed **1 unused component (`TiltCard`)** and **1 unused formatter (`signedWpa`)**. Made **24 module-internal symbols private**, including `playerWpa` and the 23 listed below. No whole component file was unused; all routed/default components remain.
- Formatting: percentages use `fmtPct`; counts/scores use `fmtInt`; seconds use `fmtSeconds` or `fmtNum` when the translated label already supplies the unit. New `fmtSignedNum` centralizes signed WPA values and avoids negative-zero output. No `.toFixed()` or `.toLocaleString()` remains in TSX components. Numeric coordinates, CSS geometry, URL identifiers and statistical calculations remain numeric.
- Low-sample UI: Home, Teams, hub map cards/map overview/player analysis, PlayerChips and PlayerWpa all use `LowSampleBanner` with one wording: **样本不足，结果仅供参考。** Inline/block variants share the same component and key.

### Removed translation keys (same list in zh.json and en.json)

- `region.T_SPAWN`
- `region.A_APPROACH`
- `region.MID`
- `region.B_APPROACH`
- `region.CT_SPAWN`
- `region.OTHER`
- `technique.jump`
- `technique.run`
- `technique.crouch`
- `technique.walk`
- `technique.stand`
- `metric.dpr`
- `metric.hs_pct`
- `metric.opening_kills_pr`
- `metric.opening_deaths_pr`
- `metric.traded_death_rate`
- `metric.avg_dist_to_team_30s`
- `metric.first_into_site_rate`
- `metric.avg_util_per_round`
- `metric.avg_early_util`
- `metric.round_win_rate`
- `metric.n_throws`
- `metric.median_pop_t_s`
- `metric_desc.kpr`
- `metric_desc.dpr`
- `metric_desc.hs_pct`
- `metric_desc.opening_kills_pr`
- `metric_desc.opening_deaths_pr`
- `metric_desc.opening_success`
- `metric_desc.traded_death_rate`
- `metric_desc.awp_share`
- `metric_desc.util_pr`
- `metric_desc.avg_dist_to_team_30s`
- `metric_desc.first_into_site_rate`
- `metric_desc.win_rate`
- `metric_desc.opening_win_rate`
- `metric_desc.avg_first_kill_s`
- `metric_desc.avg_util_per_round`
- `metric_desc.avg_early_util`
- `metric_desc.retake_win_rate`
- `metric_desc.stack_rate_15s`
- `metric_desc.round_win_rate`
- `metric_desc.n_throws`
- `metric_desc.median_pop_t_s`
- `metric_desc.ct_lane_15s_share`
- `metric_desc.t_avg_dist_to_team_30s`
- `metric_desc.t_first_into_site_rate`
- `heatmap.pick_team`
- `heatmap.low_sample`
- `tactics.description`
- `tactics.split_rate`
- `tactics.rounds`
- `tactics.median_commit`
- `tactics.insights`
- `tactics.expand_insights`
- `hub.step_map`
- `hub.step_player`
- `hub.overall`
- `hub.skip_intro`
- `hub.team_details`
- `hub.full_profile`
- `hub.player_low`
- `hub.map_help`
- `site.team_context`
- `site.rounds`
- `site.roster`
- `site.selected_players`
- `site.awaiting_sample`
- `round2.wpa_small`
- `round2.recipe_thrower`
- `round2.recipe_order`
- `round2.no_data`
- `round3.matches_title`
- `round3.matches_toggle`
- `round3.team_page_moved`
- `round3.team_page_go`

### Removed CSS selectors

`web/src/styles.css` (18 selectors):

- `.hero-copy`
- `.tag-warn`
- `.team-page > .panel`
- `.team-page .match.is-win .match-score`
- `.team-page :is(.stat-value, .ranked-count)`
- `.team-page :is(.side-t, .side-ct) .bar-fill`
- `.winprob-rounds`
- `.winprob-rounds figure`
- `.winprob-rounds figcaption`
- `.winprob-rounds svg`
- `.winprob-line`
- `.team-page.site-page :is(.side-t, .side-ct) .stat-value`
- `.team-page .tabs #tab-T[aria-selected="true"]`
- `.team-page .tabs #tab-CT[aria-selected="true"]`
- `.team-page.site-page .side-t .stat-value`
- `.team-page.site-page .side-ct .stat-value`
- `.team-page :is(.side-t) .bar-fill`
- `.team-page :is(.side-ct) .bar-fill`

`web/src/teams-hub.css` (2 selectors):

- `.hub-text-link`
- `.hub-legend`

`web/src/tactics.css` (4 selectors):

- `.team-insights details > summary`
- `.team-insights .team-insights-top`
- `.team-insights-top li`
- `.team-summary`

`web/src/heatmap.css` (2 selectors):

- `.hm-checks`
- `.hm-low`

### Private exports

- `components/PlayerWpa.tsx:playerWpa`
- `data.ts:DataState`
- `i18n.ts:getLang`
- `motion.ts:MOTION_QUERY`
- `types.ts:ExecuteTiming`
- `types.ts:Role`
- `types.ts:SparseGrid`
- `types.ts:PlacePosition`
- `types.ts:ZoneShare`
- `types.ts:HoldSpot`
- `types.ts:Tempo`
- `types.ts:Insight`
- `types.ts:ReplayPoint`
- `types.ts:ReplayEvent`
- `format.ts:isNum`
- `theme.ts:TeamPalette`
- `theme.ts:TEAM_PALETTES`
- `theme.ts:DEFAULT_PALETTE`
- `mapPlaces.ts:PlaceMarker`
- `heatmap.ts:HEAT_LAYERS`
- `heatmap.ts:PlayerColor`
- `heatmap.ts:PLAYER_COLORS`
- `heatmap.ts:GridShape`
- `components/GrenadeIcon.tsx:GrenadeIconType`

## Every changed label

All keys below were updated in both locales. Chinese before/after text is listed verbatim; the English labels carry the same units and meaning.

| Key | Before (zh) | After (zh) |
| --- | --- | --- |
| `ui.low_sample_warning` | 样本不足：目前只有 {n} 场比赛的数据，结论仅供参考。 | 样本不足，结果仅供参考。 |
| `ui.matches_title` | 比赛记录 | 地图比赛 |
| `ui.times_thrown` | 职业选手使用 {n} 次（{m} 场比赛） | 职业选手使用 {n} 次（{m} 场地图比赛） |
| `heatmap.matches` | 场数 | 地图比赛场数 |
| `heatmap.map_caption` | {matches} 场 · T {t} / CT {ct} 枪局 | {matches} 场地图比赛 · T {t} / CT {ct} 枪局 |
| `round2.wpa_duels_match` | 其中交火 {n} 回合 | 其中交火每场约贡献 {n} 个回合（按 24 回合折算） |
| `round2.wpa_match` | 每场约多赢 {n} 个回合 | 每场约多赢 {n} 个回合（按 24 回合折算） |
| `round2.wpa_pct` | 同图同阵营前 {p}% | 同图同阵营前 {p} |
| `round2.recipe_matches` | {n} 场比赛 | {n} 场地图比赛 |
| `round2.round_bar_tip` | 第 {r} 回合 · 胜率 {from}% → {to}% | 第 {r} 回合 · 胜率 {from} → {to} |
| `round3.route_label` | {via}：{p}% 的队员 | {via}：{p} 的队员 |
| `round4.archive_matches` | 本图比赛记录 · {n} 场 {w} 胜 {l} 负 | 本图比赛记录 · {n} 场地图比赛 {w} 胜 {l} 负 |

- The map-game labels count `n_matches`/match archive rows, never gun rounds. Map-game terminology clarifies that these are per-map games, not a count of best-of series.
- WPA numbers remain the existing estimates scaled to 24 rounds. The duel line now explicitly says “per match”; the UI no longer presents that estimate as an unqualified observed round count.
- Percentage placeholders now receive already-formatted percentages, so their labels no longer append a second `%`. Replay total duration now includes its seconds suffix. No match/round counter needed to be exchanged: the audited count sources already use the correct fields.

## Validation and remaining environment limits

- **PASS:** `.venv/bin/python -m pytest -q` → **196 passed, 1 skipped**, 17.22s. One pre-existing joblib warning: physical core detection fell back to logical cores.
- **PASS:** native esbuild production-mode bundle of the final edited entry point, including all TSX/CSS and imports. Used the already-installed `web/node_modules/@esbuild/darwin-arm64/bin/esbuild` with `web/src/main.tsx --bundle --format=esm --jsx=automatic`, `import.meta.env.BASE_URL="/"`, and `process.env.NODE_ENV="production"`. This verifies syntax and bundling, **not TypeScript type checking**.
- **PASS:** static checks for named relative imports/exports, literal and enumerated dynamic translation keys, JSON/placeholder parity, TSX formatting calls, CSS parsing, and Python AST parsing of `web/e2e/smoke.py`.
- `web/e2e/smoke.py` was kept aligned with grouped counts and shared sample wording. Added regression checks for keyboard seeking/playback, focus wrapping/restoration, scroll restoration, radar/dot sizing, selective player names, late fetch responses and same-duration round state reset.
- **Not run:** browser smoke and `npm run build`/`tsc`. Node/npm and Python Playwright are unavailable. A fallback localhost server failed with `PermissionError: [Errno 1] Operation not permitted`; isolated headless Chrome also could not launch (exit 134). No visual/runtime browser pass is claimed.
- Follow-up in a browser-enabled environment with the existing project toolchain: `cd web && npm run build`, serve `web/dist`, then run `python3 web/e2e/smoke.py http://localhost:4173`. Do not regenerate/sync data solely for this QA change.

The supplied directory has no `.git`, so verification used an initial source snapshot rather than a Git diff. Temporary QA build/profile/snapshot files were removed after reporting.
