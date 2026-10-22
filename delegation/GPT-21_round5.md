# GPT-21 第五轮：评审 v2 的 Bug、回放升级、HUD 风格、玩家工作流（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Desktop + Chinese only. Reviews: `delegation/inputs/review_round4a.txt` (bugs) and `review_round4b.txt` (UI/UX). Copy: `delegation/inputs/copy_round5.json` (MiniMax) → `round5` key in zh.json (en may copy zh). You have the most quota: you own verification too — after each part run `.venv/bin/python -m pytest -q` and read the code paths you touch carefully (node is not installed).

## A. Bugs (fix first)
1. **Verse glyph overlap (player slide)**: the reviewer shows two glyphs drawn on top of each other at the 4th character of a column, persisting after the entrance (after toggling layer/side buttons, which re-render). Inspect the verse DOM/CSS in `TeamsHub.tsx` / `teams-hub.css` (per-character spans, keys, duplicated glint/brush layers, transforms, animation restarting on re-render) and fix the root cause. Verse must not re-animate on re-render.
2. **Replay modal**: at 1440×900 the T-win-probability chart is cut off at the bottom. Switch to a two-column layout: radar left (square, fits `100vh − header − controls`), right column = event list (killfeed) + WP chart + controls; nothing may overflow the modal.
3. **Tactics left/right desync**: after switching recipes quickly the left radar title, route legend and map layers can show a different recipe than the expanded card. Make the radar derive everything from one selected-recipe state (single source of truth), keyed by recipe id.
4. **Player slide first screen**: a huge orange number is cut in half at the bottom edge at 1440×900; make the first screen end cleanly (next section shows its title, not half a number).
5. **CT setup codes** like `CT A2 M1 B1 C1` → `round5.ct_setup_fmt` (C/connector counts as mid).
6. **Portrait hover line**: use the most frequent early T **callout** (place name from the heatmap summary / zones, shown with the site's callout names) via `round5.portrait_place` instead of the coarse lane ("B 区"); keep kills per round.
7. **Route labels**: `round5.route_name` with the main choke callout (the first `via` callout that is not spawn), not "A → B" fragments.

## B. 2D replay upgrade
- Clock as CS2 round timer (`1:55` counting down from freeze end, switching to the 0:40 bomb timer after the plant) with `round5.clock_elapsed` small; `tabular-nums`.
- Player name abbreviations (first 3–4 chars) next to dots; dead players leave a grey × at the death spot for the rest of the round.
- Kill line: 1.5 s flash line from attacker to victim + a CS-style killfeed in the right column (attacker [weapon, `round5.killfeed_hs`] victim).
- Smokes drawn as translucent grey discs at real radius (~144 units → radar px via map scale) for 18 s with a ring countdown; molotovs orange area for 7 s; flashes a brief white pulse.
- Event anchors on the scrubber and WP chart (kill, smoke, plant); keyboard: Space, ←/→ 3 s, K next kill, G commit/hit (recipe commit if known, else first entry kill), P plant; hint `round5.keys_hint`.
- (No view cones: positions have no yaw.)

## C. HUD visual system (reviewer B §1–4)
- Mutually exclusive options (T/CT, phases, layers, speeds, tiers, sides) → one **segmented control** component (track with inset shadow, sliding highlight). Radii: 4–6 px for controls/nav; full pills only for status badges.
- Selected cards: thin top highlight line + subtle radial glow instead of a full 1 px green outline.
- Radar frames: transparent background with vignette mask, L-shaped crosshair corners and faint grid ticks instead of a black box in a box.
- Numbers: `font-variant-numeric: tabular-nums` site-wide for stats; units (% s 回合) at ~60 % size and lower contrast via a shared `<Num value unit>` helper.

## D. Player workflow features (reviewer B §5–9)
1. **Practice binds**: lineup card button `round5.bind_copy` copies `bind "KP_ENTER" "setpos …;setang …"` (tooltip `round5.bind_tip`); tactics recipe button `round5.recipe_bind` copies an `alias` cycle that moves through the recipe's grenades in throw order using each spot's most used lineup (`recipe_bind_tip`).
2. **Map point-and-click on lineups**: click a landing cluster to filter to it; the radar then shows throw positions of the remaining lineups; click one to select that lineup. Hint `round5.map_pick_hint`. Clear with Esc / reset.
3. **Ctrl+K command palette**: search maps, recipes (by spot names), lineups (from → to names), teams, players from loaded index data; Enter navigates. No external deps; lazy-load per-map data on demand.
4. **Ghost overlay** on player heatmaps: toggle `round5.ghost_toggle` shows the difference vs the map baseline for that side/phase (amber above, teal below; legend `round5.ghost_legend`), using `heatmaps/baseline.json`.

## Rules
No new npm deps; keep URL state, keyboard access, reduced motion; update `web/e2e/smoke.py` for new UI. Do not touch `playbook/`, data, images, `.github`, `delegation/design-skills/`.

## Deliverable
`delegation/GPT-21_report.md`: item by item done / partial / skipped and why; pytest result.
