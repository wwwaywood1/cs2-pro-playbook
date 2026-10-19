"""Browser smoke test for built sample data, using Playwright Chromium.

From the repository root:
    python scripts/sync_web_data.py --samples
    cd web && npm ci && npm run build && cd ..
    python3 -m http.server 4173 --directory web/dist
    python3 web/e2e/smoke.py [http://localhost:4173] [--shots DIR]

Install tooling with pip install -r web/e2e/requirements.txt and
python -m playwright install --with-deps --only-shell chromium.
Add a route by writing one @route(path, ready_selector) function. Desktop checks,
mobile overflow checks, console/page errors and screenshots are run automatically.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright


@dataclass
class Smoke:
    base: str
    lineups: list[dict]
    shots: Path | None = None
    failures: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checks: int = 0

    def check(self, cond: bool, msg: str) -> None:
        self.checks += 1
        print(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            self.failures.append(msg)

    def expected_count(self, side=None, min_throws=2, technique=None) -> int:
        return sum(
            1 for lineup in self.lineups
            if (side is None or lineup["side"] == side)
            and lineup["n_throws"] >= min_throws
            and (technique is None or lineup["technique"] == technique)
        )

    def watch(self, page: Page) -> None:
        page.on("console", lambda msg: self.errors.append(f"{page.url}: {msg.text}")
                if msg.type == "error" else None)
        page.on("pageerror", lambda error: self.errors.append(f"{page.url}: {error}"))


@dataclass(frozen=True)
class Route:
    path: str
    ready: str
    test: Callable[[Smoke, Page], None]


ROUTES: list[Route] = []


def route(path: str, ready: str):
    """Register one route function; the shared runner covers both viewports."""
    def register(test: Callable[[Smoke, Page], None]):
        ROUTES.append(Route(path, ready, test))
        return test
    return register


@route('#/', 'text=Mirage')
def check_home(smoke: Smoke, page: Page) -> None:
    # Home
    smoke.check("Mirage" in page.inner_text("body"), "home lists the Mirage map")


@route('#/de_mirage/lineups', '.lineup-card')
def check_lineups(smoke: Smoke, page: Page) -> None:
    # Lineups: default filter (min throws 2, all sides/types)
    n = page.locator(".lineup-card").count()
    smoke.check(n == smoke.expected_count(), f"default lineup list: {n} cards == {smoke.expected_count()} in data")
    smoke.check(page.locator(".radar .arrow-group").count() == n, "radar draws one arrow per card")
    smoke.check(page.locator(".radar image").count() == 1, "radar image element present")
    radar_loaded = page.locator(".radar image").evaluate("""element => new Promise(resolve => {
        const image = new Image();
        image.onload = () => resolve(image.naturalWidth > 0);
        image.onerror = () => resolve(false);
        image.src = element.getAttribute('href');
    })""")
    smoke.check(radar_loaded, "radar image loads successfully")

    # Side filter
    page.get_by_role("button", name="CT", exact=True).click()
    n_ct = page.locator(".lineup-card").count()
    smoke.check(n_ct == smoke.expected_count(side="CT"), f"CT filter: {n_ct} == {smoke.expected_count(side='CT')}")
    # Min throws 5
    page.fill("#filter-min-throws", "5")
    n5 = page.locator(".lineup-card").count()
    smoke.check(n5 == smoke.expected_count(side="CT", min_throws=5), f"CT + min 5: {n5} == {smoke.expected_count(side='CT', min_throws=5)}")
    # Reset, then technique = jump
    page.locator(".filter-actions button").click()
    page.select_option("#filter-technique", "jump")
    nj = page.locator(".lineup-card").count()
    smoke.check(nj == smoke.expected_count(technique="jump"), f"jump filter: {nj} == {smoke.expected_count(technique='jump')}")
    page.locator(".filter-actions button").click()

    # Card -> radar selection
    page.locator(".lineup-card").nth(2).click()
    smoke.check(page.locator(".lineup-card.is-selected").count() == 1, "clicking a card selects exactly one card")
    smoke.check(page.locator(".radar .arrow-group.is-selected").count() == 1, "the radar highlights exactly one arrow")
    # Radar -> card selection
    page.locator(".radar .arrow-group").nth(4).locator(".arrow-hit").dispatch_event("click")
    sel_card = page.locator(".lineup-card.is-selected .practice-cmd").inner_text()
    smoke.check(sel_card.startswith("setpos "), "clicking an arrow selects a card")

    # Copy button copies practice_cmd exactly
    first = page.locator(".lineup-card").first
    cmd = first.locator(".practice-cmd").inner_text().strip()
    btn = first.locator(".practice-row button")
    label_before = btn.inner_text()
    btn.click()
    clip = page.evaluate("navigator.clipboard.readText()")
    smoke.check(clip == cmd and cmd in {l["practice_cmd"] for l in smoke.lineups}, "copy button puts practice_cmd on the clipboard")
    smoke.check(btn.inner_text() != label_before, "copy button shows the 'copied' label")
    page.wait_for_timeout(1700)
    smoke.check(btn.inner_text() == label_before, "copy button label resets after 1.5s")


@route('#/de_mirage/teams/vitality', 'h1')
def check_team(smoke: Smoke, page: Page) -> None:
    # Team page: low-sample banner
    body = page.inner_text("body")
    smoke.check("1" in body and ("样本不足" in body or "Low sample" in body), "team page shows the low-sample warning")


@route('#/de_mirage/teams', 'text=Vitality')
def check_teams(smoke: Smoke, page: Page) -> None:
    # Teams and players pages render
    smoke.check("B8" in page.inner_text("body"), "teams page lists both teams")


@route('#/de_mirage/players', 'text=ZywOo')
def check_players(smoke: Smoke, page: Page) -> None:
    pbody = page.inner_text("body")
    smoke.check("狙击手" in pbody or "AWPer" in pbody, "players page shows role hints (ZywOo AWPer)")

    # Language switch persists across reload
    zh_title = page.inner_text("h1")
    page.locator("header button", has_text="EN").first.click() if page.locator("header button", has_text="EN").count() else page.locator(".lang-toggle, header button").last.click()
    page.reload()
    page.wait_for_selector("text=ZywOo")
    smoke.check(page.inner_text("h1") != zh_title and page.evaluate("document.documentElement.lang") == "en",
          "language switches to English and persists after reload")


def run_route(smoke: Smoke, case: Route, page: Page, *, mobile: bool = False) -> None:
    label = ("mobile-" if mobile else "") + case.test.__name__.removeprefix("check_")
    try:
        page.goto(f"{smoke.base}/{case.path}")
        page.wait_for_selector(case.ready)
        if mobile:
            page.wait_for_load_state("networkidle")
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            smoke.check(overflow <= 0,
                        f"375px no horizontal scroll on {case.path} (overflow {overflow}px)")
        else:
            case.test(smoke, page)
    except Exception as error:
        # Preserve the failing page and continue so one route cannot hide others.
        smoke.check(False, f"{label} ({case.path}): {error}")
    finally:
        if smoke.shots:
            try:
                page.screenshot(path=str(smoke.shots / f"{label}.png"), full_page=True)
            except Exception as error:
                smoke.check(False, f"could not capture {label}: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="http://localhost:4173")
    parser.add_argument("--shots", type=Path, help="save each route, including on exceptions")
    args = parser.parse_args()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    lineups = json.loads((root / "public/data/de_mirage/lineups.json").read_text(encoding="utf-8"))
    smoke = Smoke(args.base.rstrip("/"), lineups, args.shots)
    origin = urlsplit(smoke.base)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop = browser.new_context(viewport={"width": 1280, "height": 900})
            desktop.grant_permissions(["clipboard-read", "clipboard-write"],
                                      origin=f"{origin.scheme}://{origin.netloc}")
            page = desktop.new_page()
            page.set_default_timeout(10_000)
            smoke.watch(page)
            for case in ROUTES:
                run_route(smoke, case, page)

            mobile = browser.new_context(viewport={"width": 375, "height": 812})
            page = mobile.new_page()
            page.set_default_timeout(10_000)
            smoke.watch(page)
            for case in ROUTES:
                run_route(smoke, case, page, mobile=True)

            smoke.check(not smoke.errors,
                        f"no console errors ({len(smoke.errors)}): {smoke.errors[:3]}")
        finally:
            browser.close()

    print(f"\n{'PASS' if not smoke.failures else 'FAIL'}: "
          f"{smoke.checks} checks, {len(smoke.failures)} failure(s)")
    return 1 if smoke.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
