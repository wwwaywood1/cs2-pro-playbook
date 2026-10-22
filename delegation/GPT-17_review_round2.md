# GPT-17 外部评审第二轮（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Desktop + Chinese only. Review text: `delegation/inputs/review_round2.txt`. **Use the Chinese copy in `delegation/inputs/copy_round2.json` (written by MiniMax) for every new UI string** (add zh keys to `web/src/i18n/zh.json`, en may copy the zh text for now).

Claude already did the data side (in `playbook/`): team aliases (9z Globant→9z etc.), `event` on team match rows (from raw paths), `players.json` `T/CT.wpa.rounds_per_match` + `percentile` + `peers` (types in `web/src/types.ts`).

## 0. First
Run `.venv/bin/python -m playbook export` and `.venv/bin/python -m pytest -q`; both must pass.

## 1. Must do (frontend unless noted)
1. **Player heatmap**: remove the "总体" side for heatmaps; default T. Add time-slice buttons 开局 / 中期控图 / 下包后/残局 using the existing heatmap phases (early / mid / post in the heatmap data) with `time_help` as caption.
2. **WPA display**: headline `wpa_match` (rounds_per_match) and `wpa_pct` (percentile, hide when null → `wpa_small`); keep the duel split as small text; **do not show the utility split** (tooltip may mention it is noisy). Tooltip `wpa_tip`.
3. **Team page round chart**: replace the per-second sparkline with one bar per round (height = WP change over the round from the team's view; colour green/red; half-time divider after round 12; tooltip `round_bar_tip`). Show `event` in the match row; never print “未提供” — omit missing date/event.
4. **Lineups radar clusters**: aggregate by callout/place (one marker per place at the median landing point, size by count) when zoomed out; expand to individual clusters only for the selected place or on hover of a card.
5. **Lineup cards**: `pop_time` + `pop_tip` instead of 生效时间; the min-count input becomes three buttons `tier_all / tier_common / tier_must`; show the throw technique (`throw_*`) and draw on the radar the throw position with a short arrow for the view direction (yaw) when a card is hovered/selected (`throw_dir_tip`). Check `lineups.json` for technique / yaw fields; if yaw is missing, add it in `playbook/export.py` (`build_lineups`) from `utility.yaw`, with a pytest.
6. **Tactics recipe card**: for each core/option spot show `recipe_thrower` (most common thrower name for that spot in this recipe's rounds) and `recipe_order` (rank by median pop time). This needs data: add `thrower` and `order` to each SpotRef in `playbook/tactics.py` execute_recipes (most common `thrower_name`, median `pop_t_s`), with a pytest. Replace "比赛记录 41" with `recipe_matches`.
7. **Home**: Cache card shows `no_data` instead of empty numbers; map cards show T/CT round win split and the most used recipe instead of database counts.
8. **Team hub team slide**: smaller logo block (≤ 22% of first screen), win-rate rings colour-coded (≥ 65% strong green / gold accent, 50–65% neutral, < 48% muted red) with `best_map` / `weak_map` badges on the best and worst map.
9. **Sample size**: "持枪局样本" moves from a big stat card to small text next to the title.

## 2. Owner-approved compromises
- Verse and entrance: keep the verse and the full entrance on first visit; repeat visits in the session play the short version; make the skip button small (`skip_intro`); fix the mid-animation clipping (characters cut in half, digits cut mid-roll) — reveal whole glyphs with opacity/blur instead of hard overflow masks.
- Colour semantics site-wide: nav highlight one brand colour on every page; T data always amber, CT always blue; positive WPA green, negative dark red; team colours only on team brand elements (logo glow, rim light, portrait light).

## Rules
Do not touch `.github`, `delegation/design-skills/`, raw data or images. node/npm not installed: you cannot build — keep imports/types consistent by reading. Keep `web/e2e/smoke.py` passing or update consistently.

## Deliverable
`delegation/GPT-17_report.md`, item by item: done / partial / skipped and why; pytest result; export summary.
