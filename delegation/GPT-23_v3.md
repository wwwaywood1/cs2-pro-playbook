# GPT-23 v3：新数据指标 + 收尾（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook` (Python `.venv` with the parsed data on this Mac; React in `web/`). External plan: `delegation/inputs/review_v3_plan.txt` — many of its items are **already done** (verse glyph fix, tactics desync, segmented controls, unit de-emphasis, recipe alias script, replay two-column layout, kill lines, smoke/molotov circles, countdown, timeline anchors, Space/arrow keys). Do only the items below. You own both backend and frontend this round: write pytest for every new metric, run `.venv/bin/python -m pytest -q` and `.venv/bin/python -m playbook export` (≈5 min) at the end; both must pass.

## Owner decisions that override the plan
- Verse stays at full strength with its column wipe (do **not** set opacity 0.25).
- Do **not** use the plan's hand-made coordinate boxes for Mirage callouts (unverified numbers); the portrait line already uses the most frequent early callout from the data.
- View cones need per-second yaw, which the parsed positions do not have: **skip** (mention in report what the parser would need).

## Backend (playbook/)
1. **Route names**: `config/route_names.json` (MiniMax draft) maps choke callouts → standard names per map. In `recipe_routes` add `name`: the mapped name of the last non-site callout in `via` (fallback: the callout's display name). Ignore keys that are not callouts of that map (log them once).
2. **Recipe extras** (`tactics.json` › `recipes[]`): `entry_sync_sec` = median over rounds of |first entry time of route a − first entry time of route b| (entry = first player of that route entering the target bombsite core), null when only one route; `intent_badges` list: `"fake"` if the other-site plant rate ≥ 0.25 (plants on the other site in this recipe's rounds), `"sync_pinch"` if two routes each ≥ 20 % share and `entry_sync_sec` ≤ 3.5, `"rush"` if median first entry ≤ 8 s after the commit start window (define precisely in DESIGN.md).
3. **Player 6-axis profile** (`players.json` › `T/CT.radar_6d`, each 0–100 percentile among players of the same map and side with ≥ 50 rounds, plus raw values): entry (share of rounds with the opening kill or death), trade (share of own deaths traded within 4 s by a teammate, and of teammates' deaths the player traded), lurk distance (mean Manhattan distance to the alive teammates' centroid after 15 s and before the plant, T side only), space gain (net advance toward the enemy spawn while alive, per round), utility impact (flash assists + enemies inside a molotov radius at pop who moved > 150 units within 3.5 s), clutch WPA (1vN situations: wins minus the win probability at the moment the 1vN started, from `playbook/winprob.py` out-of-fold states). Document every definition in DESIGN.md.
4. **Replay extras** (`playbook/replay.py`): per second `t_control` (share of a 15×15 grid of walkable cells — cells that saw any player position on this map — closer to an alive T than to an alive CT), and `wpa` on each kill event (WP change from the winprob states, actor's view). Keep files small (rounded).

## Frontend (web/)
5. Route legend shows `name` (+ share); recipe card shows `intent_badges` as small status badges (Chinese copy: 含假打转点 / 多向同步夹击 / 爆弹一波流) and `entry_sync_sec` ("两路进点相差 X 秒").
6. Player view: a compact 6-axis radar chart (SVG, no deps) for the selected side with the percentile on hover; tooltips explain each axis in one line.
7. Replay: a thin "T 控图" line under the WP chart from `t_control`; kill events in the killfeed show their WPA (+x%).
8. Team list: replace coloured single-letter circles for teams without a logo by one neutral dark shield icon with the team's short name (owner will add real logos later).

Rules: no new npm deps; keep smoke (`web/e2e/smoke.py`) consistent (you cannot run a browser; Claude will). Do not touch images, `.github`, `delegation/design-skills/`.
Deliverable: `delegation/GPT-23_report.md` (done / skipped per item, test + export results, Falcons players' radar_6d on Mirage as a table).
