# GPT-09 战队 → 地图 → 选手 交互流程 + 全站专业化（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook` (Vite + React + TS in `web/`, HashRouter; Python pipeline in `playbook/`, venv at `.venv`).

## 0. Read first (design rules)
- `delegation/design-skills/uiux/.claude/skills/ui-ux-pro-max/SKILL.md` (and the files it points to) — pick a professional, data-dense esports-analytics style, dark theme.
- `delegation/design-skills/vercel/skills/web-design-guidelines/SKILL.md` — follow its accessibility / interaction rules.
- The tactics page (`web/src/pages/Tactics.tsx`, `web/src/tactics.css`) is the current reference for hierarchy: key numbers first, one primary visual, details collapsed. Grenade icons: `web/src/components/GrenadeIcon.tsx`.
Goal for the whole site: **professional and easy to understand**; desktop first (1280–1920 px), usable at 375 px.

## 1. New flow (owner's idea) — route `#/teams-hub` (link it as the main "战队 / Teams" nav entry)
1. **Team list**: grid of team cards. Click a team (e.g. Falcons) → a panel **slides in** with the team badge, recent results, and **one card per map with the team's win rate on that map**; each map card is a button.
2. **Click a map** → the team's overall numbers on that map (win rate overall / T / CT, rounds, tempo, default CT setup, the team summary paragraph `TeamProfile.summary`, top recipes linking to `#/<map>/tactics?recipe=<id>`), and the **5 players' portrait cards slide in**; each portrait is a button.
3. **Click a player** → two-column player view:
   - left: large portrait + the player's **定场诗 (intro verse)**;
   - right: big map with the player's heatmap and utility landing spots on this map, plus a **segmented slider 总体 / T / CT** that switches the map layers and the stat block (kills, deaths, ADR or whatever the data has, utility thrown, role hints, lurk/forward shares…).
- Every step keeps state in the URL (`?team=&map=&player=&side=`), Back/Forward works, Esc closes the top panel, all buttons keyboard-accessible. Slide transitions 200–300 ms, disabled under `prefers-reduced-motion`.

## 2. Images and verses — slots only, no scraped assets
- Team badge: `web/public/logos/teams/<slug>.png` if present, else a clean monogram badge (team initials, colour derived from the slug).
- Player portrait: `web/public/players/<steamid>.png` if present, else a neutral silhouette with the player name.
- 定场诗: `config/player_quotes.json` = `{ "<steamid>": { "name": "...", "zh": "...", "en": "..." } }` (create it with `{}`); export copies it to the site data; the UI hides the verse block when a player has none. The owner will supply the verses, logos and portraits later; do not download any.

## 3. Data
Use the existing exports first: `data/site/heatmap_teams.json`, `<map>/heatmaps/teams/<slug>.json`, `<map>/teams/<slug>.json`, `<map>/players.json`, `<map>/tactics.json`. If a number the UI needs does not exist (e.g. per-side player stats, per-map team win rate in one index file), add it to `playbook/export.py` with a pytest, then run `.venv/bin/python -m pytest -q` and `.venv/bin/python -m playbook export` and make sure both pass. Also update `web/src/types.ts` and `samples/site` if the sample data needs the new fields for the smoke test.

## 4. Rules
- No new npm dependencies; i18n zh + en for every string; reuse existing components (heatmap canvas, radar, grenade icons).
- node/npm are not installed: do not build; write strict TS. Claude builds and runs the browser checks.
- Do not touch `.github`, `delegation/design-skills/` or `data/raw`.

## Deliverable
Edit in place; write `delegation/GPT-09_report.md` listing changed files, design choices (which style from the skill and why), data added, and open questions.
