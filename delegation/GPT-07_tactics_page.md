# GPT-07 战术套路页面（派给 Codex，经 PAL clink）

---

You are working in the repo at `~/Downloads/cs2-pro-playbook` (Vite + React + TS frontend in `web/`, HashRouter). Build the **tactics page** for one map.

## Data (already exported, do not change the pipeline)
- `web/src/types.ts`: `TacticsFile`, `TTactics`, `CTTactics`, `Recipe`, `SpotRef`, `Spot`, `Insight`. `getTactics(map)` in `web/src/data.ts`.
- Sample: `samples/site/de_mirage/tactics.json`. Real data: `data/site/<map>/tactics.json` (6 maps).
- Spot display name: `name.zh` / `name.en` by current language, fall back to `label`.

## Page: route `:map/tactics` → `web/src/pages/Tactics.tsx`
1. **T overview**: tempo and target shares as horizontal bars; average commit time; split / lurk / fake rates; main lurkers.
2. **CT overview**: most common 20 s setups (`setups_20s`), forward rate and forward players, stack rate and stacked site, rotation numbers.
3. **Execute recipes** (main part): one card per recipe.
   - Card content: site, core spots (bold) and optional spots, rounds, matches, win rate, plant rate, median commit time, tempo, teams that use it.
   - Mini radar per card: the map radar image (reuse how `TeamHeatmap`/`HeatmapCanvas` loads radars) with markers at `Spot.radar_x/radar_y` (look up by `spot_id` in `TacticsFile.spots`). Smoke = grey circle, molotov = orange triangle, matching `scripts/spot_briefs.py`.
   - Clicking a spot opens its most thrown lineup: `#/<map>/lineups?id=<lineup_id>` (Lineups already supports `?id=`).
   - Controls: filter A / B / all; sort by rounds or win rate. Keep state in the URL query like the heatmap page does.
4. Add a "Tactics / 战术" link wherever the per-map links (Lineups, Teams, Players) are rendered.
5. If `TeamProfile` contains `insights: Insight[]`, show them on the team page as a short list (`text.zh` / `text.en`). If not, skip this item.

## Rules
- All UI strings go through the existing i18n (`web/src/i18n`), zh and en.
- Reuse existing styles and components; no new npm dependencies; only additive changes to `types.ts` / `data.ts`.
- Must work at 375 px width without horizontal scroll.
- **node/npm are not installed on this machine: do not try to build or install.** Write strictly typed code (`strict` TS). Claude will build, run the browser smoke test and fix errors.
- Do not touch Python, data, config or `.github` files.

## Deliverable
Edit files in place, then write `delegation/GPT-07_report.md`: list of every file you created or changed, and anything you were unsure about.
