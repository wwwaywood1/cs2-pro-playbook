# GPT-22 两个遗留问题（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook`. Claude ran `python web/e2e/smoke.py` (real Chromium) after round 5: only these two desktop failures remain.

1. **Ghost checkbox during the full entrance** (`check_hub_entrance`, smoke.py ~line 685): while the player-slide entrance is still playing (`data-entrance="full"`), clicking the checkbox "对比本图同阵营职业平均" only skips the entrance; the checkbox stays unchecked. Wanted: one click both skips the entrance and toggles the checkbox (same for keyboard Space on the focused checkbox). Look at how the entrance is skipped in `web/src/pages/TeamsHub.tsx` / `teamsHubMotion.ts` (capture-phase pointer/click/keydown listeners, a state change that remounts the analysis panel or re-creates the input, `preventDefault` on the event, or an overlay that takes the click). The skip must never swallow or cancel the user's action on a real control.
   Note: Claude already removed the `useEffect` that re-read `ghost` from the URL on every params change (it reverted clicks); keep local state as the source of truth.
2. **Flaky lineups check** "clicking a callout expands its routes" (smoke.py ~line 135: `page.locator(".radar .landing-cluster").first.dispatch_event("click")` then `.radar-reset` count == 1): fails intermittently. Find whether the cluster list re-renders between the card click and the dispatch (stale element / map-link hover state / the point-and-click filter from round 5 consuming the first click), and make both the code and the test deterministic (e.g. wait for the cluster layer to settle; one click on a cluster must always expand it).

Rules: no new deps; you cannot run a browser here — reason from the code and keep `web/e2e/smoke.py` consistent; run `.venv/bin/python -m pytest -q`. Do not touch `playbook/`, data, images.
Deliverable: `delegation/GPT-22_report.md` (cause + fix for each).
