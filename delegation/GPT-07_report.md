# GPT-07 tactics page report

## Files created
- `web/src/pages/Tactics.tsx` — adds `:map/tactics`: T tempo/target share bars, commit/split/lurk/fake statistics and main lurkers; CT 20-second setups, forward players, stacks and rotation statistics; execute recipe cards with all requested metrics, tempo and teams.
- `web/src/tactics.css` — uses the existing panel, bar, filter and statistic styles; adds responsive recipe/radar layouts, spot symbols and focus/hover states.
- `delegation/GPT-07_report.md` — this report.

## Files changed
- `web/src/App.tsx` — registers the tactics route.
- `web/src/components/Layout.tsx` — adds Tactics / 战术 to the per-map navigation alongside Lineups, Teams and Players.
- `web/src/pages/Team.tsx` — displays the optional `TeamProfile.insights` list in the current language; hides it when absent or empty.
- `web/src/i18n/en.json` — adds the navigation label and 46 tactics translation strings.
- `web/src/i18n/zh.json` — adds the corresponding Chinese translations.

## Behavior and validation
- `site=all|A|B` and `sort=rounds|win_rate` live in the URL query. Defaults/invalid values are canonicalized with history replacement; control changes retain unrelated query parameters and support browser navigation.
- Recipes sort descending with deterministic round-count/ID tie breakers. Exported arrays are not mutated.
- Radar coordinates come from `TacticsFile.spots` by `spot_id`, using the existing `BASE_URL + radars/<map>.png` convention and `_lower.png` for lower-floor spots. Grey circles represent smoke; orange triangles represent molotovs. Numbered markers correspond to core (bold) and optional spot lists.
- Both radar markers and spot names open `#/<map>/lineups?id=<lineup_id>`. The lineup is chosen by maximum `n_throws` from the full spot's lineup list, falling back to the recipe reference when necessary. Missing lineup references remain plain text/markers.
- Localized spot names fall back to the exported label. Empty arrays, null statistics and failed radar images have fallback displays.
- Read-only Python checks passed: both locale files parse; English/Chinese key sets and interpolation placeholders match; all literal translation calls in the affected components resolve.
- Checked all 7 currently exported maps: 75 recipes and 342 recipe spot references, with no missing spots, missing preferred lineup IDs or out-of-range radar coordinates. The sample Mirage export has no recipes; the empty state handles it.
- No dependency installation or Node/npm build was attempted, per task instructions. No Python source, exported data, config, pipeline, dependencies or `.github` files were changed. Existing `types.ts` / `data.ts` contracts were sufficient.

## Uncertainties and remaining handoff checks
- TypeScript compilation and browser behavior remain unverified on this machine. Run the frontend build and browser smoke test in the build-capable environment.
- Specifically verify English/Chinese switching (including team insights), shared/invalid queries, Back/Forward, A/B filters and both sorts, marker/list deep links, empty recipes and failed radar images, and document width at 375 px. Layout rules use shrinking grid tracks and wrapping text, but no browser viewport measurement was performed.
- Lower-floor radar support follows the existing heatmap convention; the currently exported recipe spots are all on level 0, so lower-floor behavior needs a suitable fixture to exercise.
