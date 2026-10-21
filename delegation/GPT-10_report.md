# GPT-10 — Cinematic Falcons showcase

Implemented in place in `/Users/stephen/Downloads/cs2-pro-playbook`.

## Changed files

- `web/src/pages/TeamsHub.tsx` — directional slide lifecycle, per-team accent table, animated numeric values and progress arcs, staged portrait cards, cinematic player bio and bilingual verse rendering, animated side indicator, heat texture crossfades, and asynchronous focus restoration.
- `web/src/teams-hub.css` — viewport-scale desktop deck, centered team identity, map backdrop and five-player row, tall portrait / analysis split, typography, accent lighting and grid, responsive layouts, and shared motion/reduced-motion rules.
- `web/e2e/smoke.py` — updated numeric assertions for accessible animated values; added exact count completion, forward/reverse slide direction, live reduced-motion behavior, and rapid Escape interruption checks. These browser checks are prepared but were not executed here.
- `delegation/GPT-10_report.md` — this report.

Regenerated local output: `data/site/` and `web/public/data/` using the existing exporter and sync command. Both quote registries now match `config/player_quotes.json`; both asset registries discover the Falcons logo and all five supplied portraits. No Python pipeline or config changes were needed. The sync command also refreshed existing cached radars in `web/public/radars/`.

## Delivered experience

- `#/teams-hub?team=falcons`: centered, oversized logo and tracked team name; map cards enter 70 ms apart, with large match-win percentages and thin SVG progress arcs. Latest results remain available in a disclosure.
- Add `&map=de_mirage`: a large dimmed radar appears behind the overview; overall/T/CT round wins and commit time count up; the five most-played portraits rise into a full-width row 75 ms apart. Hover/focus lifts the selected card, with team rim lighting and subdued neighboring portraits. The interactive team heatmap, layer controls, and floor selector remain in a disclosure below the roster.
- Add `&player=<steamid>`: a tall portrait occupies approximately the left half, fading into the background. The supplied Chinese verse reveals character by character above the player name. The Chinese original remains visible in both UI languages; an empty English translation produces no extra line. Right-side analysis retains the map, side/layer/floor controls, sample warnings, weighted stats, utility markers, role information, and detail links.
- Falcons uses `#2ecc71`. Other named teams use the color table; unlisted teams use amber. Missing logos retain monograms and missing portraits retain silhouettes.

## Motion system

- `useSlideRoute` leaves the old React tree mounted for a **320 ms WAAPI exit**, then presents a **520 ms CSS entrance**. Forward exits left / enters from right; Back/Escape reverses that direction. URL/history updates immediately. A newer destination cancels the pending animation, and rapid Escape uses the current URL depth.
- Team logo: **700 ms**, blur **20 px → sharp**, scale **1.08 → 1**, opacity reveal. Map cards: **560 ms**, 70 ms stagger. Portraits: **600 ms**, 75 ms stagger. Radar/light reveal: **700 ms**, finite rather than continuously moving.
- Numbers: **650 ms WAAPI clock/easing**, with rAF writing only the visual numeric text. Screen readers receive the exact final value throughout. Null values remain dashes.
- Verse: **300 ms** per character with bounded delays; the final character completes within **700 ms**. Screen readers receive one complete verse rather than individual characters.
- Side pill: **420 ms** indicator slide. Heat layers retain the outgoing textures for a real **420 ms crossfade**, including transitions to an empty side. Radar geometry stays fixed. Rapid changes replace pending fades.
- Shared easing: `cubic-bezier(.2,.8,.2,1)`. No animation blocks input. Timers, animation frames, observers, and WAAPI exits clean up on replacement/unmount.
- CSS and a live `matchMedia` listener honor `prefers-reduced-motion`, including preference changes during an exit/count-up: show final route, numbers, verse, arcs and heatmap immediately; disable transitions, entrance animations and hover motion/blur.

## Navigation and accessibility

Preserved team/map/player/side URL state, reload/history behavior, breadcrumbs, Escape, native keyboard controls, weighted data calculations and evidence links. Focus restoration now waits for asynchronous player cards/headings and opens substitute disclosures before focusing their cards. Desktop panels use viewport minimum heights and expand for disclosures or constrained windows; mobile stacks the player columns and keeps content scrollable.

Buttons retain 44 px targets and visible focus. Decorative assets are paired with visible names. Animated numeric/verse duplicates are hidden from assistive technology. Normal text and accent colors on the solid UI surfaces have a calculated minimum contrast of **5.69:1**; active-pill text also exceeds **4.5:1**. Portrait scrims and opaque verse panels protect text over images. Final composed visual contrast/layout still requires browser review.

Re-read `delegation/design-skills/uiux/.claude/skills/ui-ux-pro-max/SKILL.md`, its quick reference, and professional checklist. Ran focused `reduced motion continuity --domain ux` and `animation cleanup refs --stack react` searches. Applied the brief's explicit cinematic choreography, timings and easing alongside the skill's contrast, interruption and reduced-motion guidance.

## Verification

- `.venv/bin/python -m playbook export` — exit 0; six maps, 229 map matches exported.
- `.venv/bin/python scripts/sync_web_data.py` — exit 0; production data copied into the web public directory.
- `.venv/bin/python -m pytest -q` — **140 passed, 2 skipped**, exit 0.
- `python3` + `tinycss2` — stylesheet rules and declarations parse without errors.
- Python AST validation — updated browser smoke script parses successfully.
- Data/i18n checks — all **475** zh/en keys match, literal hub translation keys resolve, exported and synced quotes equal the config, and all five quoted player IDs resolve to indexed PNGs. Falcons Mirage's five leading players match the supplied portraits.
- Manual TS review against the existing strict `web/tsconfig.json`; no new npm dependencies or lockfile edits.

## Remaining reviewer checks

Per the task, **no frontend build, TypeScript compilation, or browser execution was performed**; `node`/`npm` are unavailable here. Claude should build and review:

1. The production Falcons → Mirage → each of the five players at 1280×900, 1440×900 and 1920×1080, in zh/en. Check tall portrait cropping, quote placement, backdrop dimming, hover lift, and full primary radar visibility.
2. Browser Back/Forward, reload, breadcrumb close and rapid Escape, including toggling reduced motion during a pending exit/count-up and switching sides rapidly.
3. Nuke floor switching, empty/low-sample layers, substitute focus restoration, missing-asset fallbacks, 375 px portrait and short landscape windows.
4. Run the updated sample-data smoke suite using its existing setup instructions. Restore production data afterward with `.venv/bin/python scripts/sync_web_data.py`; the sample registry intentionally has no Falcons showcase assets/verses.

This checkout has no `.git` directory; source changes were reviewed against temporary pre-edit copies. No commits, new dependencies, image moves, or edits to `.github`, `delegation/design-skills/`, or `data/raw`.

## Round 2

Applied only the three reported smoke-test fixes and portrait cropping.

### Changed files

- `web/src/pages/TeamsHub.tsx` — navigation actions now read the current HashRouter query directly from browser history. With `v7_startTransition`, history can advance before React renders; rapid Escape presses previously reused the outgoing player route and could close the player twice instead of closing player → map. Close buttons and patches now use the latest destination too.
- `web/e2e/smoke.py` — CT selection and Back assertions now wait for the rendered `aria-pressed` state as well as the URL. This removes the race between synchronous history changes and deferred React commits. The player deep-link readiness selector was already `.hub-player-view`; its later `.hub-map-card` timeout came from the rapid-Escape check, addressed by the navigation fix above. Direct player links still render the player slide immediately, without an intermediate map-card slide.
- `web/src/teams-hub.css` — the search grid uses a shrinkable `minmax(0, 1fr)` track and its input has `min-width: 0`, preventing its intrinsic width from overflowing the 375px team list. Portraits share `object-fit: cover`, `object-position: 70% 20%`, and a static 1.65× zoom anchored at the same point. The existing clipped frames remove the left-edge badge/flags/logo in both cards and the player slide. Removed desktop/mobile overrides that recentered the player portrait. Position alone would not crop the nearly matching source/frame aspect ratios.
- `delegation/GPT-10_report.md` — appended this section.

### Verification and remaining checks

- Re-read the requested UI/UX skill, responsive/motion guidance and checklist; reviewed `HashRouter` configuration, slide lifecycle and smoke assertions.
- Inspected all five supplied portraits; no image files were edited or moved.
- `python3` AST validation of `web/e2e/smoke.py` passed. Recursive `tinycss2` parsing of stylesheet rules and declarations passed.
- Reviewed the focused diff against temporary pre-edit copies. No dependencies, data, i18n strings, motion timings or unrelated files changed.
- Per the same rules, no build, TypeScript compilation or browser smoke run was performed. Reviewer: rebuild and rerun `python web/e2e/smoke.py` against the served sample build; verify CT/Back, direct player links with rapid Escape, and 375px overflow. Review all five portrait crops on desktop and mobile with production assets.
