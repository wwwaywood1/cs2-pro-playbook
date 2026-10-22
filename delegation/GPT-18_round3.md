# GPT-18 第三轮：战队页合并、进点路线、地图与文字联动（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Desktop + Chinese only. New UI strings: use `delegation/inputs/copy_round3.json` (written by DeepSeek) — add them under a `round3` key in `web/src/i18n/zh.json` (en may copy the zh text).

## 0. First
Claude added entry routes in `playbook/tactics.py` (`recipe_routes`, exported as `tactics.json` › `recipes[].routes`, type `RecipeRoute` in `web/src/types.ts`; see DESIGN.md "Entry routes"). Run `.venv/bin/python -m pytest -q` and `.venv/bin/python -m playbook export`; both must pass, and `data/site/de_mirage/tactics.json` must contain `routes`.

## 1. Merge the team detail page into the hub (owner-approved)
- The team-on-map slide (`#/teams-hub?team=X&map=Y`, `web/src/pages/TeamsHub.tsx`) gets a collapsed section `round3.matches_title` / `round3.matches_toggle` below the player row, containing the match list with event names and the per-round WP bars currently on `web/src/pages/Team.tsx` (reuse `MatchWinprob`, two-column grid, W/L tag).
- Anything else unique to `Team.tsx` (data-basis details, heatmap link) moves into that slide too, collapsed.
- `#/<map>/teams/<slug>` becomes a redirect to `#/teams-hub?team=<slug>&map=<map>` (keep old links working; preserve Back behaviour by using replace). Update every internal link (Teams list, Tactics "使用该套路的战队", heatmap pages) to point at the hub. Remove the now-unused page code.

## 2. Entry routes on the tactics map
- For the selected recipe draw `routes` on the radar under the grenade icons: smooth polyline through `points`, stroke width 2–6 px by `share`, T amber with decreasing opacity per route, an arrowhead at the end, a small label at the last third `round3.route_label` (`via` joined with " → ", share as %). Legend title `round3.routes_title` with tooltip `round3.routes_tip`; `round3.routes_none` when empty.
- Animate the stroke drawing (dash offset, 600 ms) on recipe change; static under reduced motion.

## 3. Map ↔ text linking, site-wide
- Every list row that refers to something on a map highlights it on the radar while hovered/focused, and vice versa: recipe spot rows ↔ grenade icons (tactics), lineup cards ↔ markers (lineups — partly exists, unify), player-heatmap holds/places ↔ the place, team summary spot links ↔ spot on the tactics map. Use one shared hook/context (e.g. `useMapLink`) instead of per-page code; hovered item gets a ring + slight scale, others dim to 50 %.
- Show `round3.hover_hint` once per page as small muted text.

## Rules
No new npm deps; node/npm not installed — you cannot build: keep imports/types consistent by reading. Keep `web/e2e/smoke.py` passing or update consistently (team page redirect!). Do not touch `.github`, `delegation/design-skills/`, raw data or images.

## Deliverable
`delegation/GPT-18_report.md`: item by item done / partial / skipped and why; pytest and export results.
