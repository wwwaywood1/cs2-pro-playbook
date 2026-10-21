# GPT-10 Falcons 样板：高级 PPT 式的电影感界面（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Target: the teams hub (`web/src/pages/TeamsHub.tsx`, `web/src/teams-hub.css`) with **Falcons as the showcase**: `#/teams-hub?team=falcons` → `&map=de_mirage` → `&player=<steamid>`.

Owner feedback: the UI is not cool enough. The finished product should feel like a **very high-end keynote deck**: slides that enter with motion, blur-to-sharp reveals, staged (staggered) entrances, a clear focal point per "slide".

## Assets now available
- Team logo: `web/public/logos/teams/falcons.png` (green Falcons mark, transparent).
- Portraits: `web/public/players/<steamid>.png` for karrigan, NiKo, TeSeS, kyousuke, m0NESY (dark-teal studio cards, roughly 4:5).
- Verses (定场诗): `config/player_quotes.json` → exported to the site data; zh only for now (hide the en line when empty).

## Direction
- Treat each level as a **full-viewport slide** (desktop 1280–1920 px): team → map → player. Moving forward plays an exit for the current slide and an entrance for the next; Back reverses it.
- **Team theme**: derive the accent from the team (Falcons green ≈ `#2ecc71`, keep it as a per-team colour table with the amber fallback). Use it for glows, rules and key numbers on that team's slides.
- **Team slide**: big logo centred, entering from blur(20px)+scale(1.08)+opacity 0 to sharp; team name in large tracking-wide type; the map cards fly in staggered (60–80 ms apart) and show the map win rate as a large number with a thin progress arc.
- **Map slide**: the map radar fades in large in the background (dimmed); key numbers count up from 0; the five portraits slide up in a row, staggered, each with a soft team-colour rim light; hover lifts and sharpens the hovered portrait and slightly blurs/dims the others.
- **Player slide**: left half = full-height portrait (cropped tall, gradient fade into the background) with the verse typeset vertically or as a large calligraphic-feel line that **types / fades in character by character**, then the player name; right half = the map, side switch (总体 / T / CT as a sliding pill with an animated indicator) and stats that count up. Switching side cross-fades the heatmap layers.
- Subtle ambient details are welcome (slow-moving gradient light, fine grain/noise overlay, thin grid lines) but keep text contrast AA and the data readable.
- Motion: CSS transitions/keyframes and the Web Animations API only (no new npm deps). Durations 300–700 ms, easing `cubic-bezier(.2,.8,.2,1)`; everything disabled under `prefers-reduced-motion` (show the final state immediately).
- Keep all data, URL state, Esc/Back behaviour and keyboard access from GPT-09. Other teams use the same templates with their colour (amber fallback, monogram when no logo).

## Rules
- No new npm dependencies; i18n zh + en; node/npm not installed — do not build, write strict TS; Claude builds and checks in a browser.
- Do not touch `.github`, `delegation/design-skills/`, `data/raw`; do not commit or move the images.
- Re-read `delegation/design-skills/uiux/.claude/skills/ui-ux-pro-max/SKILL.md` for motion and contrast rules.

## Deliverable
Edit in place; write `delegation/GPT-10_report.md` (changed files, the motion system you built, anything unsure).

---

## Round 2 (Claude ran `python web/e2e/smoke.py` against the sample build: 49 checks, 3 failures)

1. `FAIL CT segment changes selected state and URL` (player slide, sample team vitality).
2. `FAIL hub_player (#/teams-hub?team=vitality&map=de_mirage&player=76561198113666193&side=CT)`: waiting for `.hub-map-card` to be visible timed out after 10 s — a deep link straight to the player slide must render without first showing the map cards (or the test must wait for the player slide instead; fix whichever is wrong).
3. `FAIL 375px no horizontal scroll on #/teams-hub (overflow 22px)` — the team list slide overflows at 375 px.

Also: the supplied portraits carry a "Player" badge, flags and a logo on their left edge. In the player slide and the portrait cards, crop the portrait to the face/torso (`object-fit: cover; object-position: 70% 20%` or similar) so those badges are cut off.

Fix in place (you can reason from `web/e2e/smoke.py`; it needs a served build so you cannot run it). Append "Round 2" to `delegation/GPT-10_report.md`.
