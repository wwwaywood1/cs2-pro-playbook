# GPT-14 外部评审第一轮修改（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Desktop + Chinese only (mobile and English are out of scope for now). The full external review is in `delegation/inputs/review_round1.txt` (Chinese; figure numbers: 1 home, 2 hub team Falcons, 3 hub team-on-map Mirage, 4/5 player NiKo overall/T, 6 tactics Mirage, 7 lineups Mirage, 8 team page Falcons). Read it, then implement the items below (Claude's triage; skip anything not listed).

Already done by Claude: the Falcons logo is now a transparent PNG — remove any white plate / box behind team logos and use a large soft radial team-colour glow (≈15% opacity) instead.

## A. Hierarchy
1. Fig 1/7/8: move the big stat numbers into a compact HUD strip on the title row (right side); give the first screen to the main content.
2. Fig 3: inactive portraits = opacity 40% + grayscale, active = full colour + team back-light; no heavy blur. Shrink/raise the portrait row ~15% so names are fully visible at 1440×900.
3. Fig 6 recipe card: stats as one row of compact pills on top; core vs optional spots in two columns; tempo as a three-segment stacked bar with labels.
4. Fig 8 match list: two-column grid, each row with W/L colour tag, event name and date if available, opponent, score.

## B. Premium feel
5. Team pages use the team palette everywhere (rings, highlight bars, key numbers); non-team accents become white/silver. No amber inside a team context.
6. Verse (fig 4/5): remove the rounded black box; solid white serif characters, generous letter spacing, a thin gold/green vertical rule beside it; keep the brush reveal.
7. Portraits: remove the contour-hugging green drop-shadow; instead a large blurred (≈80px) team-colour light blob behind the figure and a subtle darkening at the edges.
8. Fig 7 lineups radar: when more than 50 lineups match, do not draw all trajectories; show landing clusters / heat by default and draw only the hovered or selected lineup's throw→landing arc (animated).

## C. Understandable data
9. Fig 7 lineup cards: hovering a card highlights its throw point and landing point on the radar; tooltip on "生效时间" = "回合开始后平均第 X 秒爆开".
10. Fig 4/5 player map: layers strictly separate — 站位/驻守/交火 show only the heatmap; 道具落点 shows only grenade icons (optional "叠加道具" toggle). Add a tiny legend (low→high scale; icon meaning). Under each stat add a comparison tag vs the player's team-mates or vs all players on the map (e.g. "队内第 1", "高于全图平均 +12%"), computed from existing exports (`players.json`, heatmap summaries) — label what it is compared with.
11. Fig 6 tactics map: for the selected recipe draw thin lines from each grenade's most common throw position (from the lineup it links to) to its landing; rename 夹击率 to a plain label that matches its definition in `tactics.json` definitions (check the DEFINITIONS text) and add a tooltip with the definition.
12. Fig 3/8 team summary: make the spot names in the summary sentence (and the signature recipe) clickable → `#/<map>/tactics?recipe=<id>`, plus a "查看该套路落点 →" button.

## Rules
No new npm deps; keep URL state, keyboard access, reduced-motion behaviour; keep `web/e2e/smoke.py` passing or update it consistently. node/npm not installed: do not build. No Python changes unless item 10 truly needs a new exported number (then add a pytest and run `.venv/bin/python -m pytest -q` and the export). Do not touch `.github`, `delegation/design-skills/`, raw data or images.

## Deliverable
Edit in place; write `delegation/GPT-14_report.md` (item-by-item: done / partially / skipped and why).
