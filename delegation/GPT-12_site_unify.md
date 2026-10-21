# GPT-12 全站统一成战队页的风格（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. The teams hub (`web/src/pages/TeamsHub.tsx`, `web/src/teams-hub.css`, `web/src/pages/teamsHubMotion.ts`) is now the design reference: cinematic slide entrances, blur-to-sharp reveals, pointer parallax/tilt/spotlight, odometer numbers, three-colour palette (primary / secondary gold / tertiary steel) with fixed T orange and CT blue. **Chinese version first.** Desktop first (1280–1920 px).

## Goal
Bring every other page to the same look and feel so the site reads as one product:
- Home (`Home.tsx`), Tactics (`Tactics.tsx`, `tactics.css`), Lineups (`Lineups.tsx`), Teams list/Team page (`Teams.tsx`, `Team.tsx`), Players (`Players.tsx`), Team heatmaps (`HeatmapTeams.tsx`, `TeamHeatmap.tsx`, `heatmap.css`), shared `Layout.tsx`, `styles.css`.

## How
1. **Extract a shared design system** from the hub: move tokens (colours, type scale, radii, shadows, easing, durations) into `web/src/theme.css` (CSS custom properties) and the reusable motion pieces (slide/reveal on mount, staggered children, count-up/odometer, tilt + specular, cursor spotlight, parallax layer, reduced-motion handling) into `web/src/motion.ts` + small components in `web/src/components/` (e.g. `Reveal`, `Stagger`, `CountUp`, `TiltCard`, `Spotlight`). Refactor the hub to use them (no visual change there).
2. **Apply per page**, keeping each page's data and URL behaviour unchanged:
   - Home: a hero "deck cover" (site title, the seven maps as large tilt cards entering staggered with each map's radar as background), then entry points to 战队 / 战术 / 道具库.
   - Tactics: key numbers as odometer counters, map radar reveal blur→sharp, recipe rows enter staggered, selected recipe card with tilt; keep the one-screen map rule from GPT-08.
   - Lineups, Players, Teams/Team, heatmaps: same header pattern (eyebrow + large title + one-line context), key-number strip, staggered list/card entrances, same buttons/pills/segmented controls as the hub.
   - Page-to-page navigation: a short cross-fade/slide between routes.
3. Palette: pages without a team context use the site palette (amber primary `#f2b134`, gold secondary, steel tertiary); pages with a team context (Team, TeamHeatmap) use that team's palette from the hub's table.
4. Keep the grenade icons, map sizing rules, accessibility (focus, 44 px targets, AA contrast), `prefers-reduced-motion` → static.

## Rules
No new npm deps; keep i18n keys (zh polished, en may lag); node/npm not installed — do not build; keep or update `web/e2e/smoke.py` selectors consistently. Do not touch `.github`, `delegation/design-skills/`, `data/raw`, images, or the Python pipeline.

## Deliverable
Edit in place; write `delegation/GPT-12_report.md`: changed files, the shared system you extracted, per-page changes, anything unsure.
