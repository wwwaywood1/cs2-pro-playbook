# GPT-09 — Team → map → player flow

Implemented in place in `/Users/stephen/Downloads/cs2-pro-playbook`.

## Delivered behavior

- Main **战队 / Teams** navigation opens `#/teams-hub`.
- Searchable team cards → team panel with badge, latest indexed scores, and one map button per map showing **map-match win rate**.
- Map selection → overall/T/CT round win rates, round samples, average commit time, `TeamProfile.summary`, collapsed tempo/default CT setup/top recipes, and portrait buttons for the five most-played players. Additional recorded players remain available in a disclosure.
- Player selection → portrait/optional intro verse on the left; primary radar, heatmap, utility landing rings, and Overall/T/CT segments on the right. Includes presence/holding/fights/utility layers, Nuke floor control, combat and utility rates, low-sample warnings, and collapsed role/landing details.
- Team, map, player, and side are URL state. Back/Forward and reload restore those selections. Escape closes one level. Native buttons, visible focus, breadcrumbs, and focus restoration support keyboard navigation.
- Local PNG slots use deterministic monograms or neutral silhouettes when absent. The empty verse registry is ready for owner content; a missing translation hides its verse independently.
- Recipe links use `/<map>/tactics?recipe=<id>`; landing links use the existing lineup `?id=` parameter.

## Design choices and skills

Read:

- `delegation/design-skills/uiux/.claude/skills/ui-ux-pro-max/SKILL.md`, `references/quick-reference.md`, and `references/pro-rules.md`.
- `delegation/design-skills/vercel/skills/web-design-guidelines/SKILL.md`.
- Existing `web/src/pages/Tactics.tsx`, `web/src/tactics.css`, and shared grenade/heatmap components.

Ran the required design-system query (`esports analytics dark dashboard`, density 8), a focused style query (`analytics dashboard dense`), and React focus/navigation guidance. Selected the verified **Data-Dense Dashboard** style (`data-dense-dashboard`) over the broad generator's glassmorphism suggestion: compact KPI grids and restrained dark surfaces fit analytical work better. Retained the existing navy/amber identity and system fonts; added readable secondary text, tabular numbers, consistent borders, and shared desktop widths. Key numbers lead, the radar is the primary visual, and supporting evidence is collapsed.

Panels enter over 240 ms; reduced motion disables animation. Layouts adapt to 375px with stacked player columns and wrapped controls. Shared navigation now has 44px targets, a skip-to-content control, and consistent keyboard focus.

The required fresh Vercel guideline fetch was attempted with `curl`; DNS resolution for `raw.githubusercontent.com` failed. The local skill and UI/UX reference rules informed implementation; a fresh upstream guideline audit is still pending.

## Data additions

Additive fields in each `heatmap_teams.json` map entry:

- `map_win_rate`: maps won / maps played.
- `round_win_rate`, `win_rate_T`, `win_rate_CT`, `all_rounds`, `low_sample`.
- `results`: up to five score records per map, ordered by source match ID.

Existing `rounds.T/CT` remains the **gun-round** sample. Round wins are weighted by rounds, rather than averaging side rates. Player side stats already exist in heatmap summaries and are reused; Overall heatmaps and rates weight each side by its sample. Utility is labeled **landings per round**, matching the cleaned data, and role hints are explicitly labeled map-wide.

`config/player_quotes.json` exports to `player_quotes.json`. `asset_slots.json` lists PNGs actually supplied under `web/public`, avoiding missing-image requests for every placeholder. Re-export and sync after adding images or verses; instructions are in `web/public/ASSETS.md`. No assets were downloaded or verses invented. Schema 1 remains compatible through optional hub fields.

## Changed files

| Files | Change |
| --- | --- |
| `web/src/pages/TeamsHub.tsx` | New complete flow, URL selection, keyboard behavior, player analysis and asset fallbacks |
| `web/src/teams-hub.css` | Responsive dashboard, panels, portraits, segments, motion and focus |
| `web/src/App.tsx` | Register hub route |
| `web/src/components/Layout.tsx` | Main Teams link, primary-nav label, skip control, map-route detection |
| `web/src/styles.css` | Shared contrast, widths, targets, focus, numbers and reduced motion |
| `web/src/data.ts`, `web/src/types.ts` | Quote/asset loaders and additive data contracts |
| `web/src/i18n/zh.json`, `web/src/i18n/en.json` | All hub and shared-accessibility copy in both languages |
| `playbook/export.py` | Map-win metadata, score index, validated quote export and supplied-image registry |
| `config/player_quotes.json` | Empty owner quote registry |
| `tests/test_team_hub.py` | Seven regression cases covering denominators, empty samples, Unicode quote lifecycle/validation, and asset discovery |
| `samples/site/heatmap_teams.json` | Compatible sample hub metadata and results |
| `samples/site/player_quotes.json`, `samples/site/asset_slots.json` | Empty sample registries |
| `web/e2e/smoke.py` | Hub list/team/map/player routes, keyboard selection, history/reload/Escape/focus, reduced motion and viewport checks |
| `web/public/ASSETS.md` | Owner slot and regeneration instructions |
| `DESIGN.md` | Data contract and sample-denominator documentation |
| `delegation/GPT-09_report.md` | This report |

Generated local output: re-exported `data/site/` and synced it plus cached radars to `web/public/`. These directories are already ignored by the repository.

## Verification

- `.venv/bin/python -m pytest -q` — **140 passed, 2 skipped**, exit 0.
- `.venv/bin/python -m playbook export` — exit 0; all six maps exported (229 map matches, 39 indexed teams).
- `.venv/bin/python scripts/sync_web_data.py` — exit 0; current production data and cached radar images copied into `web/public`.
- Python syntax checks passed for export, regression tests, and the extended browser smoke script.
- Structural checks passed for production, sample, and synced hub references and round totals; all 475 zh/en translation keys match and literal hub keys resolve.
- Manually reviewed strict TS imports, shared component props and data contracts. **No TypeScript compilation, frontend build, or browser execution was performed**, as required by the brief; node/npm are absent.

Claude's next verification: sync samples, build with the existing npm toolchain, serve the built site, then run `web/e2e/smoke.py`. The suite covers the four hub stages at 375px and 1280px, plus a 1920px player overflow check. Restore production data with `scripts/sync_web_data.py` afterward.

## Open questions / data limits

- The owner still needs to supply badges, portraits and bilingual verses.
- Recorded matches have source IDs but no reliable date field. Scores are labeled “latest indexed results,” with the ordering explained; true chronological ordering requires dates upstream.
- The displayed five are ranked by this map's recorded gun rounds, not asserted to be the current official roster.
- Combat and utility rates use the cleaned gun-round sample; ADR is not available. Utility markers show retained top clusters, not every throw.
- Frontend/browser validation and the fresh upstream Vercel guideline audit remain for the build-capable reviewer.

No new npm dependencies. `.github`, `delegation/design-skills/`, and `data/raw` were not modified.


## Round 2

Applied only the three Round 2 review items:

- **Viewport layout:** selecting a team replaces the large hero with a compact breadcrumb/title row. The player name and map share a row with Overall/T/CT; the bio column is 300 px with a 4:5 portrait and verse below. Four compact KPIs and layer/floor controls sit above the radar. Radar width is `min(column width, 100vh - measured document top - 24px)`, updated by ResizeObserver and viewport resize, with a full-width stacked mobile layout. Map help/legend is collapsed; low-sample and empty-layer notices remain visible. The team-on-map workspace places its compact overview/roster beside a radar using the existing round-weighted `team_grid` and the same sizing rule.
- **Utility icons:** player landings use shared `GrenadeGlyph` silhouettes at approximately 24 CSS px, with `GRENADE_COLORS` and translucent coverage discs below. Smoke/molotov coverage uses existing radar scale metadata, matching the tactics page's 144/120 world-unit radii; other markers retain a small translucent disc. No colored-ring markers remain in the hub.
- **Shared navigation:** every page exposes 战队 / Teams → 地图 / Maps → 战术 / Tactics → 道具库 / Lineups → 选手 / Players → 战队热力图 / Team heatmaps. Per-map links resolve the map route or validated `?map=` selection (including the heatmap page), retain that map across navigation, and otherwise default to the first index map. Chinese navigation now uses the requested 战队 label; existing English translations are reused.

Changed files:

- `web/src/pages/TeamsHub.tsx`
- `web/src/teams-hub.css`
- `web/src/components/Layout.tsx`
- `web/src/i18n/zh.json`
- `delegation/GPT-09_report.md`

Validation: Python checks confirmed all 475 zh/en translation keys match, literal translation keys in the changed TSX resolve, and all six navigation entries are unconditional and ordered as requested. `tinycss2` parsed the stylesheet, nested rules, and declarations without errors. Manually reviewed strict TS props/imports, radar coordinate alignment, side/floor filtering, focus handling, mobile wrapping, and reduced-motion rules. No data/schema changes or new dependencies. No build or TypeScript compilation was run; node/npm are unavailable. This checkout has no `.git` directory, so changes were reviewed against temporary pre-edit file copies rather than Git.

Pending reviewer check: verify the team-on-map and player workspaces at 1440×900 in both languages, including Nuke's floor selector and a supplied verse, plus 375 px wrapping and navigation through hub/map/heatmap routes. Browser rendering was not exercised here. The requested upstream Vercel guideline fetch again failed DNS resolution; local design guidance was used.
