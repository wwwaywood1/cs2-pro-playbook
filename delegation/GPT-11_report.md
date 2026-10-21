# GPT-11 — Motion, team palettes, and the verse entrance

Implemented in place in `/Users/stephen/Downloads/cs2-pro-playbook`, on top of GPT-10 and its round 2. Chinese presentation is the primary treatment.

## Changed files

- `web/src/pages/TeamsHub.tsx` — team palettes, free-standing portrait markup, map previews, rolling digit counters, vertical couplets, player entrance composition, side-coloured heat textures, and the motion hooks.
- `web/src/pages/teamsHubMotion.ts` — new delegated spring pointer system, portrait-transfer animation, and interruptible/session-aware entrance lifecycle.
- `web/src/teams-hub.css` — layered stages and portraits, depth/tilt/specular/spotlight treatments, palette roles, full/short choreography, responsive layouts, and live reduced-motion styles.
- `web/src/i18n/zh.json` and `web/src/i18n/en.json` — paired `hub.skip_intro` key; Chinese skip copy reads “跳过出场 · 任意点击或按键”. Other English copy is unchanged.
- `web/e2e/smoke.py` — updated exact-number selectors for the odometer; added map preview/tilt, preference interruption, seeded Chinese couplet, full/short/skipped entrance, and post-entrance side-roll/heat-texture checks.
- `delegation/GPT-11_report.md` — this report.

## Portraits and interactivity

- Removed the old `object-position`, cover crop, and 1.65× zoom. Images now use their native 1000×666 ratio with `object-fit: contain`, transparent surfaces, and no portrait-card border. The row and bio size the complete asset as an independent layer; the stage boundary clips overflow, rather than cropping inside a portrait frame. Missing assets retain the existing silhouette fallback.
- Pointer springs run in one delegated `requestAnimationFrame` loop, writing CSS variables without React pointer rerenders. The loop stops when settled. Mouse input on fine-pointer devices drives the effect; touch retains normal scrolling and tap controls.
- Player-stage depths: grid/background light move in the opposite direction (up to ~8 px), outline name ~4 px, portrait ~10 px, foreground dust ~14 px, and foreground labels/controls ~2–4 px. The roster has separate light/portrait depths. Spring targets use a 12 px base.
- Map cards, portrait buttons, and stat tiles tilt up to 4° per axis with a moving soft specular highlight. Primary map/player buttons also attract toward the pointer by up to 8 px. A low-opacity spotlight follows across panel/bio surfaces. Exit, pointer cancellation, window blur, and document hiding reset the springs; preference changes and unmount remove listeners/styles and cancel the frame.
- Map hover/focus fades in the matching radar thumbnail and replays the win-rate arc. Portrait hover/focus sharpens, enlarges, lifts, and adds the team rim light; neighboring portraits shrink, blur 2 px, and darken. Names remain neutral and legible.
- Clicking an available, loaded portrait captures its visible bounds. On entry, a non-interactive copy of the same transparent image grows toward the bio in a 600 ms transform animation, then disappears over the actual portrait. Fallback/deep-link entries use the regular dolly sequence. Input, scroll, resize, reduced motion, and unmount clean up the transfer.
- Counters now use individual vertical digit reels, rolling from the previous displayed digits to the exact formatted target (560 ms plus 22 ms digit stagger). Rapid changes cancel prior reels and snapshot their intermediate digits. Screen readers receive one exact final value throughout. Side changes continue rolling after the entrance has settled or been skipped.

## Colour system

- Every named team now has `primary`, `secondary`, and `tertiary`, with a complete fallback palette. Falcons uses **#2ecc71 / #e8b75a / #9aafc7**.
- Primary marks brand/active moments and portrait rims. Secondary colours key numbers and the verse. Steel tertiary colours chart arcs and overall data; backgrounds and body text remain neutral. Duotone primary/secondary light is localized behind the portrait.
- T orange and CT blue are fixed independently of the team, including overview side stats, selected-side player numbers, side pill, radar glow, and actual heatmap texture colours. Overall heatmaps use steel. Existing weighted values, geometry, floor/layer controls, grenade semantics, and the 420 ms retained-texture crossfade remain intact.
- Calculated solid-surface text/palette contrast, including maximum white specular contribution, has a **4.91:1** minimum. Neutral labels over a conservative white radar + spotlight + highlight model have a **4.74:1** minimum; dark active-fill text has a **6.52:1** minimum. The number arc has a dark backing and the verse has a dark scrim. Browser visual review is still needed for the final composite.

## Verse entrance

First entrance lasts **2500 ms**, with all content immediately available by clicking or pressing any key:

1. Primary/secondary light sweeps across a dark stage; a 24vw outline name slides behind the portrait.
2. Portrait rises, sharpens from 14 px blur, and settles from scale 1.06 to 1 (260 ms delay, 900 ms animation).
3. The Chinese couplet appears as right-to-left columns using `writing-mode: vertical-rl` and `"Songti SC", "STSong", "Noto Serif SC", serif`. Characters wipe through an irregular brush mask from 820 ms, with bounded staggering and a gold glint.
4. Name and role arrive from 1400 ms; analysis slides in from 1670 ms and digits roll. The verse scales down to a quiet .78-size vertical column by the end.

The same player re-enters in **600 ms** within the tab session, including after reload. `sessionStorage` has an in-memory fallback. A visible, localized skip button also supports keyboard activation; removing a focused skip button returns focus to the heading. The key/click listeners never prevent default actions, so Escape, breadcrumbs, links, and controls retain their behavior. Escape still closes one URL level; rapid Escape still reads current browser history as fixed in GPT-10 round 2.

Live `prefers-reduced-motion` cancels the sequence, reels, transfer, route animation, and springs; presents final content immediately; and disables hover translation/scale/blur, animated previews/arcs, glints, and heat fades. The radar preview becomes a static faint background. No preference change replays an already-settled entrance.

## Verification performed

- Recursive `tinycss2` parsing of stylesheet rules, nested media/keyframes, and declarations: passed.
- Python AST parsing of `web/e2e/smoke.py`: passed.
- JSON parsing, zh/en key parity (**476 keys**), and literal hub translation-key resolution: passed.
- Contrast calculations described above: passed after brightening the radar-preview labels.
- All five supplied portraits inspected for dimensions/mode: **1000×666 RGBA**. NiKo visually inspected using a temporary downscaled copy outside the repository. Original images were not modified.
- Reviewed the source diff against `/tmp/gpt11-before/`, strict TypeScript configuration, native keyboard/focus/URL hooks, animation cancellation, and React StrictMode effect replay. The number smoke checks now inspect the exact final value and `data-rolling`, rather than concatenating hidden digit tracks.

## Remaining checks / uncertainty

As explicitly requested, **no npm build, TypeScript compilation, or browser smoke execution was performed**. `node`/`npm` are unavailable, and the local Python environment does not have Playwright. Claude should build and run the prepared smoke suite using its existing sample-data setup. Those browser assertions are added, not reported as passing.

Review production Falcons → Mirage → all five portraits at 1280×900, 1440×900, 1920×1080, and 375 px; verify the transfer and verse clear the faces, the 2.5 s/0.6 s timing feels right, and no horizontal overflow appears. System Chinese serif availability varies by OS. Single-line owner copy (TeSeS) is balanced into two columns without changing the stored text; punctuation-separated couplets split at their punctuation. Both preserve the exact original as the accessible text.

Also exercise rapid side changes, Back/Forward/reload, rapid Escape, live reduced motion during each animation, Nuke floor switching, substitute focus restoration, missing portraits/quotes, and low/empty sample layers. A portrait that has not finished loading uses the normal entrance rather than a transfer.

No new dependencies, generated build/data output, or image changes. No edits to `.github`, `delegation/design-skills/`, or `data/raw`. This checkout has no `.git` directory, so no commit was created.
