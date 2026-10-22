# GPT-19 第四轮：评审修正 + 2D 回合回放（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Desktop + Chinese only, Falcons is the showcase. New strings: `delegation/inputs/copy_round4.json` (DeepSeek) → `round4` key in `web/src/i18n/zh.json` (en may copy zh).

## 0. First
Claude changed the pipeline (see DESIGN.md "Entry routes" and `playbook/replay.py`): recipe spots carry `throw_place`, `throw_place_share`, `thrower_team`; routes merge half-way paths and drop detours; export writes 2D replays to `data/site/<map>/replay/<demo_id>/<round>.json` + `replay/index.json`, and recipe `examples[].replay`. Types: `ReplayRound`, `ReplayEvent` in `web/src/types.ts`. Run `.venv/bin/python -m pytest -q` and `.venv/bin/python -m playbook export` (≈ 5 min); both must pass; check a replay file exists. Then copy `data/site` into `web/public/data` the same way as last round.

## 1. Review fixes (all verified by Claude)
1. **Hub team-on-map slide**: "节奏、CT 默认阵型与常用配方" appears twice (TeamsHub.tsx line ~168 and TeamDetails.tsx ~259). Keep one. Replace the stack of plain accordions below the players with 3 summary cards that expand: `round4.archive_matches` (n, wins, losses), `round4.archive_details`, `round4.archive_heatmap` (link). Each card shows a one-line preview when collapsed.
2. **Player map, grenade layer**: when the layer is 道具落点, replace the heat gradient legend with grenade icons + `round4.util_legend`; clicking a grenade icon draws its most common throw position and trajectory (lineup refs on the spot → `lineups.json` throw/landing) on the radar.
3. **Lineups radar clusters**: the number in a cluster must be the count of lineups in the current filter (`round4.cluster_count`), not summed historical throws; size the circle by that count; avoid overlap (min distance / simple collision push or merge clusters closer than their radii). Numbers must stay legible.
4. **Tactics recipe spots**: list core/options **sorted by `order`** (throw order; unknown last). Under each spot show `round4.throw_from` with the callout name of `throw_place` (callout names come from the map config / spot names already used elsewhere), and `round4.thrower_example` as small muted text (`thrower`, `thrower_team`). Do not present the player as "the" thrower.
5. **Home map cards**: the whole card opens `#/<map>/tactics`; add a small secondary button `round4.map_to_lineups`. Cache: greyed card with `round4.coming_soon` badge, not clickable; the HUD count stays the number of maps with data.
6. **Player portraits (hub map slide)**: on hover/focus show one line `round4.portrait_line` (T early main lane from the heatmap summary, kills per round) under the name.

## 2. 2D round replay (new)
- Component `web/src/components/RoundReplay.tsx` (canvas or SVG, no deps): radar image of the map, 10 dots (T amber, CT blue, player name on hover; dead players disappear with a small × at the kill spot), interpolate positions between seconds for smooth motion; events appear at their time: kill markers, grenade icons (reuse `GrenadeGlyph`) with a short fade, the plant. Controls: play/pause, speed 1×/2×/4×, a scrubber, time `round4.replay_time`. Under the map a small T-win-probability line (`wp_t`) with a playhead. Title shows teams, round number, winner. Esc / close button closes. Respect reduced motion (no auto-play).
- Entry points: (a) tactics recipe card "示例回合" rows with `replay: true` get a `round4.replay_open` button; (b) on the hub match archive, clicking a round bar of the per-round WP chart opens that round (check `replay/index.json`). Open as a modal overlay; keep URL state `&replay=<demo_id>:<round>` so Back closes it.

## Rules
No new npm deps; node/npm not installed — you cannot build, keep imports/types consistent by reading. Keep `web/e2e/smoke.py` passing or update it consistently (add a replay open/close check). Do not touch `.github`, `delegation/design-skills/`, raw data or images.

## Deliverable
`delegation/GPT-19_report.md`: item by item done / partial / skipped and why; pytest and export results.
