"""Browser smoke test for the static site (headless Chromium via Playwright).

    cd web && npm run build && python3 -m http.server 4173 --directory dist &
    python3 e2e/smoke.py [http://localhost:4173] [--shots DIR]

Needs sample data in web/public/data (python scripts/sync_web_data.py --samples) before
the build. Checks every route for console errors, the lineup filters, radar/card
selection, the copy button, the low-sample banner, language switching, and 375px layout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:4173")
SHOTS = Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
ROOT = Path(__file__).resolve().parents[1]
LINEUPS = json.loads((ROOT / "public/data/de_mirage/lineups.json").read_text(encoding="utf-8"))

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def expected_count(side=None, min_throws=2, technique=None) -> int:
    return sum(
        1 for l in LINEUPS
        if (side is None or l["side"] == side) and l["n_throws"] >= min_throws
        and (technique is None or l["technique"] == technique)
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    # Home
    page.goto(f"{BASE}/#/")
    page.wait_for_selector("text=Mirage")
    check("Mirage" in page.inner_text("body"), "home lists the Mirage map")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "home.png"))

    # Lineups: default filter (min throws 2, all sides/types)
    page.goto(f"{BASE}/#/de_mirage/lineups")
    page.wait_for_selector(".lineup-card")
    n = page.locator(".lineup-card").count()
    check(n == expected_count(), f"default lineup list: {n} cards == {expected_count()} in data")
    check(page.locator(".radar .arrow-group").count() == n, "radar draws one arrow per card")
    check(page.locator(".radar image").count() == 1, "radar image element present")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "lineups.png"), full_page=False)

    # Side filter
    page.get_by_role("button", name="CT", exact=True).click()
    n_ct = page.locator(".lineup-card").count()
    check(n_ct == expected_count(side="CT"), f"CT filter: {n_ct} == {expected_count(side='CT')}")
    # Min throws 5
    page.fill("#filter-min-throws", "5")
    n5 = page.locator(".lineup-card").count()
    check(n5 == expected_count(side="CT", min_throws=5), f"CT + min 5: {n5} == {expected_count(side='CT', min_throws=5)}")
    # Reset, then technique = jump
    page.locator(".filter-actions button").click()
    page.select_option("#filter-technique", "jump")
    nj = page.locator(".lineup-card").count()
    check(nj == expected_count(technique="jump"), f"jump filter: {nj} == {expected_count(technique='jump')}")
    page.locator(".filter-actions button").click()

    # Card -> radar selection
    page.locator(".lineup-card").nth(2).click()
    check(page.locator(".lineup-card.is-selected").count() == 1, "clicking a card selects exactly one card")
    check(page.locator(".radar .arrow-group.is-selected").count() == 1, "the radar highlights exactly one arrow")
    # Radar -> card selection
    page.locator(".radar .arrow-group").nth(4).locator(".arrow-hit").dispatch_event("click")
    sel_card = page.locator(".lineup-card.is-selected .practice-cmd").inner_text()
    check(sel_card.startswith("setpos "), "clicking an arrow selects a card")

    # Copy button copies practice_cmd exactly
    first = page.locator(".lineup-card").first
    cmd = first.locator(".practice-cmd").inner_text().strip()
    btn = first.locator(".practice-row button")
    label_before = btn.inner_text()
    btn.click()
    clip = page.evaluate("navigator.clipboard.readText()")
    check(clip == cmd and cmd in {l["practice_cmd"] for l in LINEUPS}, "copy button puts practice_cmd on the clipboard")
    check(btn.inner_text() != label_before, "copy button shows the 'copied' label")
    page.wait_for_timeout(1700)
    check(btn.inner_text() == label_before, "copy button label resets after 1.5s")

    # Team page: low-sample banner
    page.goto(f"{BASE}/#/de_mirage/teams/vitality")
    page.wait_for_selector("h1")
    body = page.inner_text("body")
    check("1" in body and ("样本不足" in body or "Low sample" in body), "team page shows the low-sample warning")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "team.png"), full_page=True)

    # Teams and players pages render
    page.goto(f"{BASE}/#/de_mirage/teams")
    page.wait_for_selector("text=Vitality")
    check("B8" in page.inner_text("body"), "teams page lists both teams")
    page.goto(f"{BASE}/#/de_mirage/players")
    page.wait_for_selector("text=ZywOo")
    pbody = page.inner_text("body")
    check("狙击手" in pbody or "AWPer" in pbody, "players page shows role hints (ZywOo AWPer)")
    if SHOTS:
        page.screenshot(path=str(SHOTS / "players.png"), full_page=True)

    # Language switch persists across reload
    zh_title = page.inner_text("h1")
    page.locator("header button", has_text="EN").first.click() if page.locator("header button", has_text="EN").count() else page.locator(".lang-toggle, header button").last.click()
    page.reload()
    page.wait_for_selector("text=ZywOo")
    check(page.inner_text("h1") != zh_title and page.evaluate("document.documentElement.lang") == "en",
          "language switches to English and persists after reload")

    # 375px: no horizontal scroll on every route
    m = browser.new_context(viewport={"width": 375, "height": 812})
    mp = m.new_page()
    for route in ["#/", "#/de_mirage/lineups", "#/de_mirage/teams", "#/de_mirage/teams/vitality", "#/de_mirage/players"]:
        mp.goto(f"{BASE}/{route}")
        mp.wait_for_load_state("networkidle")
        overflow = mp.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(overflow <= 0, f"375px no horizontal scroll on {route} (overflow {overflow}px)")
    if SHOTS:
        mp.goto(f"{BASE}/#/de_mirage/lineups")
        mp.wait_for_selector(".lineup-card")
        mp.screenshot(path=str(SHOTS / "mobile-lineups.png"))

    check(not errors, f"no console errors ({len(errors)}): {errors[:3]}")
    browser.close()

print(f"\n{'PASS' if not failures else 'FAIL'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
