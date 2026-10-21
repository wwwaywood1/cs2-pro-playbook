# GPT-11 灵动感、配色体系、定场诗出场（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Continue the cinematic teams hub (`web/src/pages/TeamsHub.tsx`, `web/src/teams-hub.css`), Falcons as the showcase. **Chinese version first**: polish zh; en can lag behind (keep keys, no need to tune English copy).

Owner feedback on GPT-10:
1. Not lively / interactive enough.
2. Team-colour theming is a good idea but the page is now one flat colour.
3. The verse (定场诗) is bolted on — not cool.

## New portraits (replace the crop hacks)
`web/public/players/<steamid>.png` are now Claude-processed cut-outs: **transparent background**, 1000×666, all faces the same size (≈250 px tall) with the face centre at **y = 300**, bottom 220 px fading to transparent, 2× super-resolved and colour-matched. Remove the `object-position` cropping from GPT-10 round 2; place them as free-standing layers (no card frame needed) so light, text and particles can sit behind and in front of them.

## 1. Interactivity / liveliness
- Pointer parallax on the player slide and portrait row: background grid/light, big name text, portrait and foreground UI move at different depths (max 8–16 px), spring-smoothed.
- Cards (map cards, portraits, stat tiles) tilt 3–6° toward the pointer with a moving specular highlight; magnetic hover on primary buttons.
- A soft spotlight follows the cursor across dark surfaces.
- Hover on a map card previews that map: radar thumbnail fades in behind the card with the win-rate arc animating.
- Portrait row: hovering a player brings them forward (scale + sharpen + rim light), others recede (blur 2px, darken); click plays a short "step forward" transition into the player slide (shared-element feel: the portrait grows into the left half).
- Side switch 总体 / T / CT: besides the sliding pill, the stat numbers roll (odometer) to the new values and the heatmap colour shifts per side.
- All of this under `prefers-reduced-motion` → static.

## 2. Colour system (not monochrome)
Per team define a palette, not a single accent:
- `primary` (team colour, Falcons green `#2ecc71`) for brand moments: logo glow, rim light, active state;
- `secondary` complementary accent (for Falcons a warm gold `#e8b75a`, matching the jersey trim) for key numbers and the verse;
- `tertiary` cool neutral (steel blue/grey) for charts and secondary data;
- T side and CT side keep their own fixed hues (T warm orange, CT blue) in side-specific data, independent of the team.
Use gradients sparingly (duotone light leaks behind the portrait mixing primary and secondary). Text stays neutral white/grey; check AA contrast.

## 3. 定场诗 as an entrance sequence (player slide)
Choreograph it as a title sequence, ~2.5 s total, skippable by any click/key:
1. Dark stage, primary/secondary light leak sweeps in; huge outline player name (e.g. "NiKo", 20–28 vw, stroke only, low opacity) slides in behind the portrait.
2. Portrait rises and sharpens from blur (dolly-in feel, scale 1.06 → 1).
3. Verse appears in large Chinese type (serif/calligraphic feel via system fonts: `"Songti SC","STSong","Noto Serif SC",serif`), **vertical writing** (`writing-mode: vertical-rl`) beside the portrait, each character revealed with a brush-like mask wipe and a gold (secondary) glint passing through; the two halves of the couplet appear as two columns.
4. Name and role settle; stats panel slides in from the right and numbers roll up.
After the sequence the verse stays as a quiet vertical column; re-entering the same player within the session plays a shortened version (0.6 s).

## Rules
No new npm deps (CSS, WAAPI, pointer events, requestAnimationFrame only); keep URL state, Esc/Back, keyboard access, smoke selectors (or update `web/e2e/smoke.py` consistently). node/npm not installed: do not build; Claude builds and checks. Do not touch `.github`, `delegation/design-skills/`, `data/raw`, or the images.

## Deliverable
Edit in place; write `delegation/GPT-11_report.md` (changed files, how each point was done, anything unsure).

---

## Round 2 (Claude's review at 1440×900, Falcons → Mirage → NiKo)

1. **Verse columns are broken**: in the final state the two vertical columns overlap — the left column's characters are squashed on top of each other ("负尽狂名十五年" unreadable) and the verse box is tiny next to the portrait. Each column must show its characters at full size with normal vertical spacing (no overlapping spans, no negative margins); give the verse a proper block (font-size ≈ 40–48 px, column gap ≈ 1 em), placed right of the face, not over the outline name.
2. **Portrait is enlarged too much** (only the face is visible and it looks soft). The cut-outs are 1000×666; never display them larger than their native pixels at the current devicePixelRatio (`max-width: calc(1000px / dpr)`, i.e. ~500 CSS px on Retina, ~700 CSS px max), keep the whole bust visible (head to shoulders), bottom aligned to the slide floor.
3. Keep the outline name behind the portrait, but it should not collide with the verse.
4. (Later, not now) 375 px overflow on the hub and player slide — leave for the mobile pass.

Append "Round 2" to `delegation/GPT-11_report.md`.
