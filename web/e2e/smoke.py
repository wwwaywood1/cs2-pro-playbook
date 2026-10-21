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

from playwright.sync_api import Page, expect, sync_playwright


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


@route('#/teams-hub', '.hub-team-card')
def check_teams_hub(smoke: Smoke, page: Page) -> None:
    page.locator('#hub-team-vitality').focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('#hub-map-de_mirage')
    smoke.check('team=vitality' in page.url, 'hub team selection is in URL')
    smoke.check(page.locator('.hub-map-card strong .sr-only').first.inner_text() == '100%',
                'sample Vitality map card shows map wins, not round wins')
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-map-card .hub-count')].every(
        el => el.dataset.rolling === 'false' && el.querySelector('.sr-only').textContent === el.querySelector('.hub-number-final').textContent)""")
    smoke.check(True, 'animated map rates settle on the exact exported values')
    page.locator('#hub-map-de_mirage').click()
    page.wait_for_selector('.hub-player-card')
    smoke.check(page.locator('.hub-stage').get_attribute('data-direction') == 'forward',
                'entering a map uses forward slide direction')
    smoke.check(page.locator('.hub-player-card').count() == 5, 'map shows five portrait buttons')
    steamid = page.locator('.hub-player-card').first.get_attribute('id').removeprefix('hub-player-')
    page.locator('.hub-player-card').first.focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-player-view')
    smoke.check(f'player={steamid}' in page.url and 'map=de_mirage' in page.url,
                'player and map selections are deep linked')
    smoke.check(page.locator('.hub-verse').count() == 0, 'absent owner verse is hidden')
    page.get_by_role('button', name='CT', exact=True).click()
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('side') === 'CT'")
    # HashRouter updates history before its deferred React render commits.
    expect(page.get_by_role('button', name='CT', exact=True)).to_have_attribute('aria-pressed', 'true')
    smoke.check(page.get_by_role('button', name='CT', exact=True).get_attribute('aria-pressed') == 'true',
                'CT segment changes selected state and URL')
    page.go_back()
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('side') === 'all'")
    expect(page.get_by_role('button', name='CT', exact=True)).to_have_attribute('aria-pressed', 'false')
    smoke.check(page.get_by_role('button', name='CT', exact=True).get_attribute('aria-pressed') == 'false',
                'Back restores overall side')
    page.go_forward()
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('side') === 'CT'")
    page.reload()
    page.wait_for_selector('.hub-player-view')
    smoke.check(page.get_by_role('button', name='CT', exact=True).get_attribute('aria-pressed') == 'true',
                'reload restores player and side')
    page.keyboard.press('Escape')
    page.wait_for_selector('.hub-player-card')
    smoke.check(page.locator('.hub-stage').get_attribute('data-direction') == 'back',
                'closing a player reverses slide direction')
    page.wait_for_function('(id) => document.activeElement.id === id', arg=f'hub-player-{steamid}')
    smoke.check('player=' not in page.url and 'map=de_mirage' in page.url,
                'Escape closes player and restores portrait focus')
    page.keyboard.press('Escape')
    page.wait_for_selector('.hub-map-card')
    page.keyboard.press('Escape')
    page.wait_for_selector('.hub-team-card')
    page.wait_for_function("document.activeElement.id === 'hub-team-vitality'")
    smoke.check('team=' not in page.url, 'Escape closes map then team and restores team focus')


@route('#/teams-hub?team=vitality', '.hub-map-card')
def check_hub_team(smoke: Smoke, page: Page) -> None:
    smoke.check(page.locator('.hub-results li').count() == 1, 'team panel shows the recorded sample result')
    card = page.locator('#hub-map-de_mirage')
    card.hover(position={'x': 24, 'y': 28})
    page.wait_for_function("parseFloat(getComputedStyle(document.querySelector('#hub-map-de_mirage .hub-map-preview')).opacity) > .3")
    page.wait_for_function("Math.abs(parseFloat(document.querySelector('#hub-map-de_mirage').style.getPropertyValue('--tilt-h'))) > .5")
    smoke.check(card.locator('.hub-map-preview').get_attribute('src').endswith('radars/de_mirage.png'),
                'hover previews the selected map radar with spring tilt')
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("getComputedStyle(document.querySelector('#hub-map-de_mirage')).transform === 'none'")
    smoke.check(card.evaluate("el => getComputedStyle(el).translate") == 'none',
                'live reduced motion cancels tilt and magnetic translation')
    page.emulate_media(reduced_motion='no-preference')


@route('#/teams-hub?team=vitality&map=de_mirage', '.hub-player-card')
def check_hub_map(smoke: Smoke, page: Page) -> None:
    smoke.check(page.locator('.hub-kpis .stat').count() == 4, 'map overview shows four leading metrics')


@route('#/teams-hub?team=vitality&map=de_mirage&player=76561198113666193&side=CT', '.hub-player-view')
def check_hub_player(smoke: Smoke, page: Page) -> None:
    smoke.check(page.locator('.hub-map-figure .hm-radar').count() == 1, 'deep-linked player has one primary radar')
    smoke.check(page.locator('.hub-player-bio').count() == 1, 'deep-linked player has portrait column')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    overflow = page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
    smoke.check(overflow <= 0, '1920px player view has no horizontal overflow')
    page.set_viewport_size({'width': 1280, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-count')].every(
        el => el.dataset.rolling === 'false' && el.querySelector('.sr-only').textContent === el.querySelector('.hub-number-final').textContent)""")
    page.get_by_role('button', name='T', exact=True).click()
    page.wait_for_function("""() => document.querySelector('.hub-side-indicator') &&
        getComputedStyle(document.querySelector('.hub-side-indicator')).transitionDuration === '0s' &&
        !document.querySelector('.hub-stage').getAnimations({subtree: true}).some(a => a.playState === 'running')""")
    smoke.check(page.locator('.hub-stage').evaluate('(el) => getComputedStyle(el).animationName') == 'none',
                'reduced motion disables CSS motion and WAAPI count-ups during a side change')
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-count')].every(
        el => el.dataset.rolling === 'false' && el.querySelector('.sr-only').textContent === el.querySelector('.hub-number-final').textContent)""")
    smoke.check(True, 'reduced motion presents final numeric values immediately')
    page.emulate_media(reduced_motion='no-preference')
    page.wait_for_function("getComputedStyle(document.querySelector('.hub-side-indicator')).transitionDuration !== '0s'")
    # Exercise interruption: a queued map exit must not override a newer team close.
    page.keyboard.press('Escape')
    page.keyboard.press('Escape')
    page.wait_for_selector('.hub-map-card')
    smoke.check('map=' not in page.url and 'player=' not in page.url,
                'rapid Escape follows current URL depth without stale transition completion')
    page.emulate_media(reduced_motion='no-preference')


@route('#/teams-hub?team=vitality&map=de_mirage&player=76561198113666193&side=all', '.hub-player-view')
def check_hub_entrance(smoke: Smoke, page: Page) -> None:
    # Test owner-style copy without modifying the sample registry or production data.
    player = '76561198113666193'
    page.route('**/data/player_quotes.json', lambda request: request.fulfill(json={
        player: {'name': 'ZywOo', 'zh': '一箫一剑平生意，负尽狂名十五年', 'en': ''}
    }))
    try:
        page.evaluate('(id) => sessionStorage.removeItem(`hub-intro:${id}`)', player)
        page.reload()
        page.wait_for_selector('.hub-player-view[data-entrance="full"]')
        smoke.check(page.locator('.hub-verse-column').count() == 2,
                    'Chinese couplet enters as two vertical columns')
        smoke.check(page.locator('.hub-verse-column').first.evaluate('(el) => getComputedStyle(el).writingMode') == 'vertical-rl',
                    'verse uses vertical writing rather than a horizontal quote card')
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled', timeout=4000)
        page.wait_for_function("!document.querySelector('.hub-count[data-rolling=\"true\"]')")
        smoke.check(page.locator('.hub-verse-line .sr-only').inner_text() == '一箫一剑平生意，负尽狂名十五年',
                    '2.5-second entrance settles with one complete accessible verse')
        page.keyboard.press('Escape')
        page.wait_for_selector(f'#hub-player-{player}')
        page.locator(f'#hub-player-{player}').click()
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'short')
        page.keyboard.press('Shift')
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled')
        smoke.check('player=' in page.url, 'any key skips the shortened entrance without changing route')
        counts = page.locator('.hub-analysis-toolbar .hub-count')
        all_rounds = counts.last.get_attribute('data-value')
        before_heat = page.locator('.hub-layer-in image').first.get_attribute('href')
        page.get_by_role('button', name='CT', exact=True).click()
        expect(page.get_by_role('button', name='CT', exact=True)).to_have_attribute('aria-pressed', 'true')
        expect(counts.last).to_have_attribute('data-rolling', 'true')
        smoke.check(counts.last.get_attribute('data-value') != all_rounds,
                    'side change rolls digits to new values after the intro has settled')
        page.wait_for_function("!document.querySelector('.hub-count[data-rolling=\"true\"]')")
        smoke.check(page.locator('.hub-layer-in image').first.get_attribute('href') != before_heat,
                    'CT changes the heat texture and side hue independently of team palette')
        # Start another full entrance, then change the accessibility preference mid-flight.
        page.evaluate('(id) => sessionStorage.removeItem(`hub-intro:${id}`)', player)
        page.reload()
        page.wait_for_selector('.hub-player-view[data-entrance="full"]')
        page.emulate_media(reduced_motion='reduce')
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled')
        page.wait_for_function("!document.querySelector('.hub-stage').getAnimations({subtree: true}).some(a => a.playState === 'running')")
        smoke.check(page.locator('.hub-intro-skip, .hub-portrait-transfer').count() == 0,
                    'live reduced motion finishes the title sequence and removes transfer layers')
    finally:
        page.emulate_media(reduced_motion='no-preference')
        page.unroute('**/data/player_quotes.json')


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
