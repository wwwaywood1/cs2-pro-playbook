# GPT-20 回放审查 + 全站 QA 走查（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Desktop + Chinese only. Round 4 (GPT-19) is merged and builds.

## 1. Review and fix `web/src/components/RoundReplay.tsx`
Check and fix concrete bugs only: requestAnimationFrame/timers cancelled on unmount and when the replay changes; no stale closures on speed/time; fetch race when switching rounds quickly (ignore late responses / AbortController); modal focus trap and focus restored to the opener on close; body scroll lock restored; no autoplay under prefers-reduced-motion; keyboard: Space play/pause, ←/→ seek 1 s, Esc close. Make the radar in the modal as large as the viewport allows (square, min(70vh, modal width)), player dots 8–10 px with a 1 px dark outline, names of alive players shown on hover and for the selected/hovered player only.

## 2. QA sweep (the external reviewer asked for an "industrial-grade" cleanup)
- Unused i18n keys in `web/src/i18n/zh.json` / `en.json` (keys never referenced): list them in the report and remove them; any referenced key missing in zh → add.
- Dead CSS: selectors in `web/src/*.css` that match no class used in `web/src/**/*.tsx` → remove (be careful with dynamic class names built from template strings; keep those).
- Unused components / exports → remove.
- Number formatting consistency: percentages, seconds and counts use the helpers in `web/src/format.ts` everywhere (no ad-hoc `toFixed` in components unless it goes through a helper).
- Labels that state a unit must match the number: e.g. a card saying "场比赛" must count matches, "回合" must count rounds; list every label you changed.
- Low-sample warnings use one shared component and one wording.

## Rules
No new npm deps; node/npm not installed — keep imports/types consistent by reading; run `.venv/bin/python -m pytest -q`. Keep `web/e2e/smoke.py` consistent. Do not touch `playbook/`, data, images, `.github`, `delegation/design-skills/`.

## Deliverable
`delegation/GPT-20_report.md`: replay fixes, removed keys/CSS/components (counts + notable ones), changed labels.
