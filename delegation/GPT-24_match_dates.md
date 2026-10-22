# GPT-24 比赛时间标签（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Goal: every match (demo) gets a date so players can find matches, the site can sort by time, and later analysis can use time windows (e.g. recent form, patch eras).

Facts (checked by Claude): CS2 demo headers carry no date; HLTV RAR archives store no member timestamps; extracted `.dem` mtimes are extraction time. So dates come from the event schedule plus ordering.

## Backend
1. `config/events.json`: event date ranges (Claude, from a 2026 schedule page) keyed by event slug as found in raw paths (`playbook.dedupe.demo_events` already derives the slug/pretty name — reuse its slug logic).
2. New `playbook/dates.py`: for each demo → `{"date": "YYYY-MM-DD", "date_precision": "day" | "event", "event": name}`.
   - Within an event, order matches by `hltv_match_id` when available (HLTV ids grow with scheduling time) and spread them linearly over the event's date range → precision "day" only when the event has ≥ 3 dated ids and the estimate is within the range; otherwise the event start date with precision "event". Maps of the same series (m1/m2/m3, same archive) share one date.
   - Unknown event → `null` date (never invent).
   - Allow manual overrides `config/match_dates.csv` (`demo_id,date`) → precision "exact"; overrides win.
3. Export: add `date`, `date_precision`, `event` to `matches` rows used everywhere (team match rows in `teams/<slug>.json`, hub match archive, recipe `examples`, replay files, `index.json` per map: min/max date). Add `data_through` (latest date) to `index.json`.
4. Tests for interpolation, series sharing, overrides, unknown events. Run `.venv/bin/python -m pytest -q` and `.venv/bin/python -m playbook export`.

## Frontend
5. Show dates everywhere a match appears ("2026-05-12" or "2026-05 · PGL Astana 2026" for precision "event"; tooltip explains estimated dates).
6. Hub match archive and team match lists sorted newest first, with a time filter: 全部 / 近 3 个月 / 近 1 个月 (relative to `data_through`), segmented control style. Recipe example rounds sorted newest first.
7. Ctrl+K palette: matches searchable by opponent, event and date.
8. Home footer: "数据截至 {data_through}".

Rules: no new deps; keep `web/e2e/smoke.py` consistent; do not touch images, `.github`, `delegation/design-skills/`.
Deliverable: `delegation/GPT-24_report.md` (how many demos per precision, any events without dates, test/export results).
