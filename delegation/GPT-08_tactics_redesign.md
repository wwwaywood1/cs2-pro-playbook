# GPT-08 战术页重做：桌面优先、清晰地图、道具图标、信息分层（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook` (Vite + React + TS in `web/`). Redesign the tactics page you built in GPT-07 (`web/src/pages/Tactics.tsx`, `web/src/tactics.css`). The owner's feedback:

1. The product is a **desktop web site first** (design for 1280–1600 px); mobile comes later, so at 375 px it only needs to stay usable (stack vertically, no horizontal scroll).
2. **The map is not clear** and **the grenade markers are not self-explanatory** (you need a legend to read them).
3. The page is **cluttered, shows too much at once, and has no visual hierarchy**: the reader does not know where to look first.

## Target layout (desktop)

```
┌ Header: map name · side tabs [T 进攻 | CT 防守] ─────────────────────────────┐
│ Key numbers row: 3–4 big figures only (e.g. 最常打 A 38% · 平均进点 52 s ·     │
│ 最常用套路 正门烟+小木屋顶火 胜率 65%). One sentence of context each.         │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ ONE large radar, sticky (≈ 640–760px)│ Recipe list (compact rows, collapsed)│
│ shows the selected recipe's utility  │  ▸ A  正门烟 + 小木屋顶火 + A包点火   │
│ zoomed to that site                  │      54 回合 · 胜率 65% · 进点 48 s   │
│                                      │  ▾ (expanded row) details: options,  │
│                                      │    tempo, teams, example rounds …    │
├──────────────────────────────────────┴──────────────────────────────────────┤
│ "更多数据" collapsed sections: full tempo/target bars, lurkers, CT rotation…   │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Replace the per-card mini radars with **one big shared radar**. Hovering a row previews its utility; clicking selects it and expands the row. The first recipe is selected by default.
- **Zoom**: fit the view to the selected recipe's spots plus padding (min 35 % of the map width), with a smooth transition; a "全图" toggle shows the whole map. Render at `devicePixelRatio` so it stays sharp. Raise radar contrast slightly (e.g. CSS `filter: contrast(1.1) brightness(1.15)`) and dim everything outside the zoom box.
- CT tab: same structure — key numbers (default setup at 20 s and its win rate, forward rate, stack rate), then collapsed details.
- Team insights (`TeamProfile.insights`, `Team.tsx`): show the top 3 as short highlighted sentences, the rest behind "展开".

## Grenade icons (make our own SVG, no game assets)

Create `web/src/components/GrenadeIcon.tsx` exporting icons for `smoke`, `molotov` (also used for incendiary), `flash`, `he`. Each should be recognisable without a legend:
- smoke: grey canister with a puffy cloud;
- molotov: bottle with an orange flame;
- flash: white/yellow burst with a small grenade body;
- he: dark green round grenade with a pin.

They must read clearly at 16 px (in text lists) and at 28–32 px (on the map). Use them in the recipe list, on the map and on the lineups page (`Lineups.tsx`) wherever the grenade type is shown as text or a plain shape.

**On the map**, also draw the effect area to scale (game units → radar px via the map's scale in `config/maps/<map>.toml` / existing radar helpers): a soft translucent grey disc for a smoke (radius ≈ 144 units) and a translucent orange patch for a molotov (radius ≈ 120 units), with the icon on top. Core spots are fully opaque; optional spots are at 50 % opacity with a dashed outline. Keep the numbering in sync with the list.

## Visual hierarchy rules

- One primary focus per screen: the big map plus the selected recipe. Everything else is secondary (smaller, lower contrast) or collapsed.
- Typography scale: page title 28–32 px; key numbers 32–40 px bold; section titles 18 px; body 14–15 px; meta 12–13 px muted. At most 3 text colours (primary, muted, accent).
- Use the accent colour only for the selected item and the single most important number per block.
- Generous spacing (8 px grid), fewer borders: separate sections by space and subtle background, not by boxes inside boxes.
- Collapsed rows show at most one line of meta. All collapsible parts use `<details>`/`<summary>` or buttons with `aria-expanded`, keyboard-accessible.

## Rules

- Same data (`TacticsFile`, `TeamProfile`); no pipeline, Python, config or `.github` changes; no new npm dependencies; i18n for every string (zh + en).
- node/npm are not installed here: do not try to build. Write strict, typed code; Claude builds and runs the browser checks.
- Keep the URL state (`site`, `sort`, plus a new `recipe=<id>` and `side=T|CT`).

## Deliverable

Edit in place, then write `delegation/GPT-08_report.md`: the files changed, the design decisions you made, and anything you are unsure about.

---

## Round 2 (Claude's review of round 1 screenshots at 1440 px)

Round 1 builds cleanly and works. Fix these:

1. **Zoom is too tight.** With 2–3 core spots the map zooms into one corridor and the reader loses where on the map they are, and the 1024 px radar looks blurry when enlarged. Minimum zoom box: 60 % of the map width, centred on the selected spots but always containing the target bombsite centre. Never upscale the radar more than ~1.6× its native pixels.
2. **The map must be fully visible without scrolling.** Size the radar as `min(column width, 100vh − sticky offset − 24px)`, square, sticky. Make the key-numbers row more compact (number 32 px, label + one line, less vertical padding) so the map starts higher on a 1440×900 screen.
3. **Map markers are too busy**: icon in a dark disc inside the coverage disc. Drop the dark disc; draw the grenade icon (≈ 28 px) directly on the coverage area with a thin dark outline / drop shadow for contrast. The number badge stays small at the top right.
4. The header (logo + nav) is aligned to a narrower container than the page content; use the same max-width and side padding for both.
5. In the expanded recipe row, the meta grid (比赛记录、下包率、夹击率、平均闪光弹数) should be one compact row of 4 small stats, not a 2×2 block of large cells.

Same rules as above. Append a "Round 2" section to `delegation/GPT-08_report.md` listing the changes.
