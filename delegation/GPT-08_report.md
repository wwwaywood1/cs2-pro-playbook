# GPT-08 tactics redesign report

## Changed files

- `web/src/pages/Tactics.tsx` — desktop-first T/CT views, three/four headline metrics, one shared sticky radar, recipe hover/focus previews and selection, collapsed secondary data, scaled utility coverage, CT setup rows, example rounds, and URL state.
- `web/src/tactics.css` — 28–32 px titles, 32–36 px key figures, restrained text colors, spacious two-column desktop layout, compact recipe rows, map/selection styles, highlighted insights, and vertical stacking below 1000 px.
- `web/src/components/GrenadeIcon.tsx` — original SVG smoke canister/cloud, burning bottle, flash burst, and green HE grenade artwork. Exports the default `GrenadeIcon`, reusable `GrenadeGlyph`, and typed `GrenadeIconType`; accepts `flash`/`flashbang` and `molotov`/`incendiary` aliases.
- `web/src/components/Radar.tsx` — replaces lineup landing dots and color-only legend swatches with the shared grenade artwork; adds keyboard activation and accessible grenade/route labels to lineup arrows.
- `web/src/pages/Lineups.tsx` — adds 16 px grenade icons to type filters and lineup badges.
- `web/src/pages/Team.tsx` — highlights the first three exported insight sentences; puts the remainder behind a native, localized “展开” / “Expand” disclosure. Keeps the original fact text and export order.
- `web/src/styles.css` — shared inline icon alignment, grenade labels, badge spacing, and visually hidden accessible labels.
- `web/src/i18n/en.json`, `web/src/i18n/zh.json` — matching translations for all new controls, context, metadata, empty states, and disclosure labels; replaces the old shape-based radar instructions.
- `delegation/GPT-08_report.md` — this report.

No pipeline, Python source, config, exported data, dependency, or `.github` files changed. Existing `TacticsFile`, `TeamProfile`, `MapMeta`, and data loaders remain sufficient.

## Design and interaction decisions

- The main content area can grow to 1440 px. At 1280–1600 px, the left column gives the shared radar roughly 690–760 px of visible width, with recipe rows on the right. Below 1000 px the map and list stack; shrinking tracks, wrapping long names, and truncated collapsed summaries accommodate 375 px.
- T shows the most attacked site's share, average commit time, and the most-used recipe's win rate/name. CT shows the default 20-second setup's share and shape, its win rate, forward rate, and stack rate. Only the leading figure is accented.
- The first filtered/sorted recipe is selected and expanded by default. Pointer hover and keyboard focus preview another recipe without changing the URL. Clicking selects/expands a row; clicking the open row collapses its details while retaining map selection. Leaving the list restores the selected recipe's radar.
- Query state preserves `site=all|A|B`, `sort=rounds|win_rate`, `recipe=<id>`, and `side=T|CT`, plus unrelated parameters. Invalid/default values are canonicalized with history replacement. A recipe excluded by the site filter falls back to the first result; empty results remove the recipe parameter. CT retains the current T recipe for return navigation.
- One SVG radar animates its viewBox over 280 ms, fits the active floor's recipe spots plus coverage/padding, and never zooms tighter than 35% of the map width. A small contextual perimeter remains visible and dimmed; “全图” toggles the complete map. Reduced-motion preferences bypass animation.
- SVG is rendered by the browser at native `devicePixelRatio`; there is no fixed-resolution canvas backing store. A ResizeObserver keeps tactic icons approximately 32 CSS px while zooming/resizing. Radar contrast/brightness is raised. The underlying PNG remains limited by the supplied asset's resolution.
- Nuke uses upper/lower floor buttons with spot counts and the existing `_lower.png` convention. Original numbering survives floor filtering and matches the expanded recipe lists. Missing positions/lineups/images and unavailable scale have fallbacks.
- Smoke/fire coverage uses soft translucent radial fills. Core markers have full opacity; optional markers and coverage use 50% opacity and dashed outlines. Marker and list links retain the most-thrown lineup deep link.
- Teams/examples inside a selected recipe, map spot indexes, and the complete T/CT overview are native `<details>` disclosures. Primary recipe/setup rows use buttons with `aria-expanded` and `aria-controls`.
- CT has setup statistics and aggregate CT spots, but no per-setup utility association in the data contract. Its map therefore explicitly shows the six most-thrown CT spots for the selected site across all setups. Selecting a setup expands its explanation; it does not imply a utility association. CT site filtering affects that utility map, while setup rows remain whole-team shapes.

## How map scale was obtained

Scale was already available to the frontend: `getMeta(map)` in `web/src/data.ts` fetches `data/<map>/meta.json`, and `MapMeta.radar.scale` in `web/src/types.ts` documents game units per pixel on the 1024×1024 radar. `Tactics.tsx` now passes this positive finite value into `RecipeRadar`/`fitSpots`.

I inspected `web/public/data/de_mirage/meta.json`, which exports `radar.scale = 5.0`, and checked it against `[radar].scale = 5.0` in `config/maps/de_mirage.toml`. I also compared all seven current `data/site/<map>/meta.json` scales with their map TOML files: all match.

Coverage radius in radar coordinates is `144 / scale` for smoke and `120 / scale` for molotov/incendiary. For Mirage this is 28.8 / 24 px; for Nuke (`scale = 7`) it is approximately 20.57 / 17.14 px. The SVG viewBox scales the map and coverage together. No guessed fallback scale is used: if metadata is unavailable, icons remain and coverage is omitted with a localized notice.

## Validation performed

- Read-only Python checks passed for both locale JSON files: all 422 leaf keys and interpolation placeholders match; all 97 literal UI translation lookups in the affected components resolve. Dynamic grenade, side, tempo, and floor translation groups are present.
- Compared exported scales with TOML config for all seven exported maps; all are finite, positive, and equal.
- Checked all 75 exported recipes / 342 spot references: positions exist and are within the radar; mirrored the focus-bound calculations against the exported recipe/floor groups and verified the 35% minimum, map bounds, and containment of marker centers.
- `tinycss2` tokenization passed for both edited CSS files.
- No Node/npm build or browser execution was attempted, as explicitly requested. TypeScript and rendered layout remain unverified; the static checks above do not substitute for compilation/browser checks.

## Handoff checks and uncertainties

- In the build-capable environment, run `cd web && npm run build`, then check Chinese/English at 1280, 1600, and 375 px, including actual document overflow and Retina rendering.
- Exercise hover/focus preview restoration, row expansion, URL reload/Back/Forward, both sorts, A/B filters, T/CT switching, full-map toggling, reduced motion, and most-used lineup links.
- Check missing radar/metadata, empty recipes, long translated names, insight lists with more than three entries, and a fixture containing lower-floor/mixed-floor recipe spots. Existing recipe exports use level 0, so a lower-floor fixture is still needed to exercise that path.
- The current public/sample Mirage export has no tactics file; use the full exported site data when serving the browser checks. No data export was modified as part of this frontend-only task.
- Coverage is intentionally approximate; walls, height, and actual fire spread are not modeled. CT utility cannot be attributed to individual setup shapes with the supplied schema.
