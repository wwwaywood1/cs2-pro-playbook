"""Browser smoke test for built sample data, using Playwright Chromium.

From the repository root:
    python scripts/sync_web_data.py --samples
    cd web && npm ci && npm run build && cd ..
    python3 -m http.server 4173 --directory web/dist
    python3 web/e2e/smoke.py [http://localhost:4173] --samples [--shots DIR]

Install tooling with pip install -r web/e2e/requirements.txt and
python -m playwright install --with-deps --only-shell chromium.
Add a route by writing one @route(path, ready_selector) function. Desktop checks
(1440x900 and 1280x800), console/page errors and screenshots run automatically.
Use --samples with the committed samples/site (CI): it skips REAL_DATA_ONLY checks.
Without --samples every route runs: use that, plus --lab-only (AI lab, CT defense and
fingerprints) and --orbit-only (radial hub), against a full export before publishing.
Use --mobile to add the 375px horizontal-overflow pass (the site is desktop-first).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Page, expect, sync_playwright

# Fixtures reuse the exporter's row builders (playbook/site_index.py is stdlib-only).
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


# Owner-supplied images are gitignored, so CI and other sample builds never have them.
OWNER_ASSETS = ('map-bg/', 'logos/', 'players/')


@dataclass
class Smoke:
    base: str
    lineups: list[dict]
    shots: Path | None = None
    samples: bool = False
    failures: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checks: int = 0

    def expected_missing(self, url: str) -> bool:
        """--samples only: a 404 for an owner asset, or for a data file that the committed
        samples/site predates (the UI treats those files as optional)."""
        if not self.samples:
            return False
        path = urlsplit(url).path.removeprefix(urlsplit(self.base).path.rstrip('/')).lstrip('/')
        if path.startswith(OWNER_ASSETS):
            return True
        return path.startswith('data/') and not (REPO / 'samples/site' / path.removeprefix('data/')).exists()

    def check(self, cond: bool, msg: str) -> None:
        self.checks += 1
        print(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            self.failures.append(msg)

    def expected_count(self, side=None, min_throws=0, technique=None) -> int:
        return sum(
            1 for lineup in self.lineups
            if (side is None or lineup["side"] == side)
            and lineup["n_throws"] >= min_throws
            and (technique is None or lineup["technique"] == technique)
        )

    def watch(self, page: Page) -> None:
        def console(msg) -> None:
            if msg.type != "error":
                return
            # Chromium logs failed loads without the URL in the text; it is the message location.
            url = (msg.location or {}).get("url") or ""
            if "status of 404" in msg.text and self.expected_missing(url):
                return
            self.errors.append(f"{page.url}: {msg.text}" + (f" [{url}]" if url and url != page.url else ""))

        page.on("console", console)
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


def mock_json(page: Page, pattern: str, payload: dict | list) -> None:
    # Playwright supplies (Route, Request) to handlers accepting two arguments,
    # including a lambda's default arguments. Capture JSON in a one-argument closure.
    def fulfill(intercepted):
        intercepted.fulfill(json=payload)

    page.route(pattern, fulfill)


@route('#/', 'text=Mirage')
def check_home(smoke: Smoke, page: Page) -> None:
    # Home
    smoke.check("Mirage" in page.inner_text("body"), "home lists the Mirage map")
    overview = page.request.get(f'{smoke.base}/data/index.json').json()
    available = any(m['map'] == 'de_cache' and m['n_matches'] > 0 for m in overview['maps'])
    cache = page.locator('.map-card').filter(has_text='Cache')
    if available:
        expect(cache.locator('.map-card-main')).to_have_attribute('href', '#/de_cache/tactics')
        expect(cache.locator('.map-card-secondary')).to_have_attribute('href', '#/de_cache/lineups')
        smoke.check(cache.locator('.map-no-data').count() == 0, 'Cache home card opens real data')
    else:
        smoke.check(cache.locator('a').count() == 0 and '暂无数据' in cache.inner_text(),
                    'Cache home card has a disabled no-data state')
    mirage = page.locator('.map-card').filter(has_text='Mirage')
    expect(mirage.locator('.map-card-main')).to_have_attribute('href', '#/de_mirage/tactics')
    expect(mirage.locator('.map-card-secondary')).to_have_attribute('href', '#/de_mirage/lineups')


def check_lineup_batch(smoke: Smoke, page: Page, total: int, label: str) -> int:
    expect(page.locator('.lineup-list')).to_have_attribute('data-total-count', str(total))
    n = page.locator('.lineup-card').count()
    # A deep-linked selection beyond the first batch gets one extra mounted card.
    smoke.check(min(total, 60) <= n <= min(total, 61),
                f'{label}: {n} mounted cards, {total} total results')
    expect(page.locator('.lineup-show-more')).to_have_count(int(n < total))
    return n


@route('#/de_mirage/lineups', '.lineup-card')
def check_lineups(smoke: Smoke, page: Page) -> None:
    # All exported results remain filterable; only the first batch is mounted.
    check_lineup_batch(smoke, page, smoke.expected_count(), 'default lineup list')
    if smoke.shots:
        page.screenshot(path=str(smoke.shots / 'lineups-initial.png'), timeout=10_000)
    if smoke.expected_count() > 60:
        first_id = page.locator('.lineup-card').first.get_attribute('data-map-link')
        page.locator('.lineup-show-more').click()
        expect(page.locator('.lineup-card')).to_have_count(min(120, smoke.expected_count()))
        smoke.check(page.locator('.lineup-card').first.get_attribute('data-map-link') == first_id,
                    'show more appends the next batch without replacing existing cards')
        page.locator('.filter-actions button').click()

    bubbles = page.locator(".radar .landing-cluster text").all_text_contents()
    smoke.check(sum(int(value.replace(",", "")) for value in bubbles) == len(smoke.lineups),
                "cluster counts include every filtered lineup exactly once")
    smoke.check(page.locator(".radar .landing-cluster").evaluate_all("""rows => rows.every((a, i) => rows.slice(i + 1).every(b => {
      const ca = a.querySelector('circle:not(.map-link-ring)'), cb = b.querySelector('circle:not(.map-link-ring)');
      return Math.hypot(ca.cx.baseVal.value - cb.cx.baseVal.value, ca.cy.baseVal.value - cb.cy.baseVal.value) >= ca.r.baseVal.value + cb.r.baseVal.value;
    }))"""), "cluster circles do not overlap")
    smoke.check(page.locator(".radar .arrow-group").count() <= 1,
                "overview keeps individual routes collapsed")
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
    n_ct = smoke.expected_count(side="CT")
    check_lineup_batch(smoke, page, n_ct, "CT filter")
    smoke.check(sum(int(value.replace(',', '')) for value in page.locator('.radar .landing-cluster text').all_text_contents()) == n_ct,
                'cluster counts recompute after the side filter')
    # Usage tiers replace the free-form count input.
    page.locator("#filter-tiers button").nth(1).click()
    check_lineup_batch(smoke, page, smoke.expected_count(side="CT", min_throws=10), "common tier filters at ten throws")
    page.locator("#filter-tiers button").nth(2).click()
    check_lineup_batch(smoke, page, smoke.expected_count(side="CT", min_throws=50), "must-learn tier filters at fifty throws")
    # Reset, then technique = jump
    page.locator(".filter-actions button").click()
    page.select_option("#filter-technique", "jump")
    check_lineup_batch(smoke, page, smoke.expected_count(technique="jump"), "jump filter")
    page.locator(".filter-actions button").click()

    # Card -> radar selection
    page.locator(".lineup-card").nth(2).click()
    smoke.check(page.locator(".lineup-card.is-selected").count() == 1, "clicking a card selects exactly one card")
    smoke.check(page.locator(".radar .arrow-group.is-selected").count() == 1, "the radar highlights exactly one arrow")
    # Radar -> card selection
    # Exercise hit testing too: a hovered route must not cover the callout.
    cluster = page.locator(".radar .landing-cluster").first
    expect(cluster).to_be_visible()
    cluster.locator("circle:not(.map-link-ring)").click()
    expect(page.locator('.radar-pick-head .radar-reset')).to_have_text('× 清除地图选点')
    expect(page.locator('.radar-pick-status')).to_contain_text('已按地图选点筛选')
    smoke.check(page.locator('.radar-reset').bounding_box()['y'] < page.locator('.radar').bounding_box()['y'], 'map-pick clear action is above the radar')
    expect(page.locator(".radar .landing-cluster")).to_have_count(0)
    smoke.check(True, "one click on a callout expands its routes")
    # URL navigation is transitioned independently of the immediate local pick.
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).has('landing')")
    picked = page.evaluate("new URLSearchParams(location.hash.split('?')[1]).get('landing').split(',')")
    mounted = check_lineup_batch(smoke, page, len(picked), 'landing pick')
    smoke.check(page.locator('.radar .throw-dot').count() == mounted, 'landing pick draws the mounted batch of throw positions')
    target = page.locator('.radar .arrow-group').last
    target_id = target.get_attribute('data-map-link').removeprefix('lineup:')
    target.focus()
    page.keyboard.press('Enter')
    expect(page.locator('.lineup-card.is-selected')).to_have_attribute('data-map-link', f'lineup:{target_id}')
    page.wait_for_function("(() => { const q = new URLSearchParams(location.hash.split('?')[1]); return q.has('id') && q.has('landing'); })()")
    smoke.check(True, 'map selection is shareable in the URL')
    sel_card = page.locator(".lineup-card.is-selected .practice-cmd").inner_text()
    smoke.check(sel_card.startswith("setpos "), "clicking a callout selects its most-used lineup")
    smoke.check(page.locator(".radar .throw-direction").count() == 1,
                "selected lineup shows its recorded view direction")

    page.keyboard.press('Escape')
    check_lineup_batch(smoke, page, smoke.expected_count(), 'cleared landing pick')
    page.wait_for_function("!new URLSearchParams(location.hash.split('?')[1]).has('landing')")
    smoke.check('landing=' not in page.url, 'Escape clears the landing filter')
    page.locator('.radar .landing-cluster').first.locator('circle:not(.map-link-ring)').click()
    page.locator('.radar-reset').click()
    expect(page.locator('.radar-pick-status')).to_have_count(0)
    check_lineup_batch(smoke, page, smoke.expected_count(), 'cleared landing pick')
    smoke.check(True, 'visible clear action restores all map results')
    card = page.locator('.lineup-card').first
    key = card.get_attribute('data-map-link')
    card.hover()
    expect(page.locator(f'.radar .arrow-group[data-map-link="{key}"]')).to_have_attribute('data-map-state', 'active')
    marker = page.locator(f'.radar .arrow-group[data-map-link="{key}"]')
    marker.focus()
    page.mouse.move(0, 0)
    expect(card).to_have_attribute('data-map-state', 'active')
    smoke.check(page.locator('.map-link-hint').count() == 1, 'lineups has one shared hover hint')

    # Copy button copies practice_cmd exactly
    first = page.locator(".lineup-card").first
    cmd = first.locator(".practice-cmd").inner_text().strip()
    btn = first.locator(".practice-row button").first
    label_before = btn.inner_text()
    btn.click()
    clip = page.evaluate("navigator.clipboard.readText()")
    smoke.check(clip == cmd and cmd in {l["practice_cmd"] for l in smoke.lineups}, "copy button puts practice_cmd on the clipboard")
    smoke.check(btn.inner_text() != label_before, "copy button shows the 'copied' label")
    first.get_by_role('button', name='复制练习绑定', exact=True).click()
    bound = page.evaluate("navigator.clipboard.readText()")
    smoke.check(bound.startswith('bind "KP_ENTER" "setpos ') and ';setang ' in bound, 'lineup practice bind copies position and angles under KP_ENTER')
    # Check feedback while its card is still mounted. The sample has no >=10-throw
    # lineups, so exercising the next tier below deliberately removes this button.
    expect(btn).to_have_text(label_before, timeout=3000)
    smoke.check(True, "copy button label resets after 1.5s")
    tiers = page.locator('#filter-tiers')
    tiers.locator('button').first.focus()
    page.keyboard.press('ArrowRight')
    expect(tiers.locator('button').nth(1)).to_have_attribute('aria-pressed', 'true')
    smoke.check(tiers.locator('.segment-highlight').evaluate('el => el.getBoundingClientRect().width') > 0, 'shared segmented control supports arrows and positions its highlight')
    check_lineup_batch(smoke, page, smoke.expected_count(min_throws=10), 'keyboard tier change')

    # Loading a tail result directly must mount/select it without mounting 2,443 cards.
    if len(smoke.lineups) > 60:
        tail = sorted(smoke.lineups, key=lambda row: (-row['n_throws'], row['id']))[-1]
        page.goto(f"{smoke.base}/#/de_mirage/lineups?id={tail['id']}")
        expect(page.locator('.lineup-card.is-selected')).to_have_attribute('data-map-link', f"lineup:{tail['id']}")
        check_lineup_batch(smoke, page, smoke.expected_count(), 'tail deep link')
        smoke.check(page.locator('.radar .arrow-group.is-selected').count() == 1,
                    'tail deep link selects its radar trajectory')


@route('#/de_mirage/tactics', '.tactics-page')
def check_tactics_linking(smoke: Smoke, page: Page) -> None:
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / 'public/data/de_mirage/tactics.json').read_text())
    lineup = next(row for row in smoke.lineups if row['type'] in ('smoke', 'molotov'))
    spot = {
        'spot_id': 'smoke-test', 'side': 'T', 'type': lineup['type'],
        'place': lineup['land_place'], 'label': '测试落点', 'name': {'zh': '测试落点', 'en': '测试落点'},
        'radar_x': lineup['land']['radar_x'], 'radar_y': lineup['land']['radar_y'], 'level': 0,
        'n_throws': 20, 'lineups': [{'lineup_id': lineup['id'], 'n_throws': 20}],
    }
    recipe = {
        'id': 'test-entry', 'site': 'A', 'core': [{**spot, 'share': 1}], 'options': [],
        'n_rounds': 20, 'n_matches': 2, 'teams': [{'team': 'Vitality', 'rounds': 20}],
        'win_rate': .6, 'plant_rate': .8, 'median_commit_s': 35,
        'tempo': [{'value': 'mid', 'rounds': 20}], 'avg_flashes': 3, 'split_rate': .2, 'examples': [{'demo_id': 'smoke-replay', 'round_num': 1, 'team': 'Vitality', 'replay': True}],
        'entry_sync_sec': 2.5, 'intent_badges': ['fake', 'sync_pinch', 'rush'],
        'routes': [{'name': 'A1主攻线', 'via': ['TSpawn', 'TRamp'], 'lane': 'A', 'n': 6, 'share': .6,
                    'points': [[900, 500], [800, 600], [700, 700], [600, 720]]}],
    }
    fixture['spots'] = [spot]
    fixture['recipes'] = [recipe, {**recipe, 'id': 'test-empty', 'n_rounds': 10, 'routes': [],
                                   'entry_sync_sec': None, 'intent_badges': []}]
    # The export indexes every lineup that tactics.json references; keep that true for the fixture.
    from playbook.site_index import lineup_index_row
    index_path = root / 'public/data/de_mirage/lineup_index.json'
    lineup_index = json.loads(index_path.read_text()) if index_path.exists() else {}
    lineup_index[lineup['id']] = lineup_index_row(lineup)
    try:
        page.route('**/data/de_mirage/replay/smoke-replay/1.json', lambda request: request.fulfill(json=replay_fixture()))
        mock_json(page, '**/data/de_mirage/tactics.json', fixture)
        mock_json(page, '**/data/de_mirage/lineup_index.json', lineup_index)
        page.reload()
        page.wait_for_selector('.tactics-entry-path')
        smoke.check(page.locator('.tactics-entry-path').count() == 1, 'selected recipe draws its player entry route')
        smoke.check('60%' in page.locator('.tactics-route-row').first.inner_text(), 'entry route label includes its share')
        expect(page.locator('.tactics-route-row').first).to_contain_text('A1主攻线')
        selected_intent = page.locator('.tactics-recipe.is-selected .recipe-intent')
        expect(selected_intent).to_contain_text('两路进点相差 2.5 秒')
        badges = page.locator('.tactics-recipe.is-selected h3 .recipe-intent-badge')
        smoke.check(badges.all_text_contents() == ['🎭 假打转点', '✂️ 多向夹击', '⚡ 一波流'], 'title shows all three localized intent badges')
        page.locator('.tactics-recipe.is-selected .tactics-recipe-toggle').click()
        expect(page.locator('.tactics-recipe.is-selected .tactics-recipe-toggle')).to_have_attribute('aria-expanded', 'false')
        expect(badges).to_have_count(3)
        page.locator('.tactics-recipe.is-selected .tactics-recipe-toggle').click()
        path = page.locator('.tactics-entry-path')
        smoke.check(path.get_attribute('marker-end') is not None, 'entry route has an arrowhead')
        row = page.locator('.tactics-recipe.is-selected .tactics-spots li').first
        key = row.get_attribute('data-map-link')
        row.hover()
        marker = page.locator(f'.tactics-radar [data-map-link="{key}"]')
        expect(marker).to_have_attribute('data-map-state', 'active')
        marker.focus()
        page.mouse.move(0, 0)
        expect(row).to_have_attribute('data-map-state', 'active')
        smoke.check(page.locator('.map-link-hint').count() == 1, 'tactics has one shared hover hint')
        page.emulate_media(reduced_motion='reduce')
        smoke.check(path.evaluate("el => getComputedStyle(el).animationName") == 'none', 'reduced motion keeps entry paths static')
        for index in [1, 0, 1]:
            page.locator('.tactics-recipe-toggle').nth(index).click()
        page.locator('.tactics-recipe').first.hover()
        expect(page.locator('.tactics-radar-wrap')).to_have_attribute('data-recipe-id', 'test-empty')
        expect(page.locator('.tactics-recipe.is-selected')).to_have_attribute('data-recipe-id', 'test-empty')
        smoke.check(True, 'rapid recipe switching and hover keep the selected card, radar and routes together')
        expect(page.locator('.tactics-entry-path')).to_have_count(0)
        smoke.check('暂无路线' in page.locator('.tactics-routes-legend').inner_text(), 'empty recipe has a route-specific empty state')
        selected = page.locator('.tactics-recipe.is-selected')
        selected.get_by_role('button', name='复制整套爆弹练习脚本', exact=True).click()
        script = page.evaluate("navigator.clipboard.readText()")
        smoke.check('alias "pp_test_empty_0"' in script and 'bind "KP_ENTER" "pp_next"' in script and ';setang ' in script,
                    'recipe practice script creates a keyed alias cycle')
        selected.locator('summary', has_text='示例回合').click()
        opener = selected.locator('.replay-open')
        overflow = page.evaluate('document.body.style.overflow')
        opener.click()
        page.wait_for_selector('dialog[open] .replay-radar')
        expect(page.locator('.round-replay .replay-scrubber')).to_have_value('0')
        expect(page.get_by_role('button', name='播放', exact=True)).to_be_visible()
        page.wait_for_timeout(150)
        expect(page.locator('.round-replay .replay-scrubber')).to_have_value('0')
        smoke.check(page.locator('.replay-player').count() == 10, 'replay shows ten players and reduced motion prevents auto-play')
        scrubber = page.locator('.replay-scrubber')
        smoke.check(page.evaluate('document.body.style.overflow') == 'hidden', 'replay locks body scrolling')
        close = page.locator('.replay-close')
        close.focus()
        page.keyboard.press('Shift+Tab')
        expect(page.locator('.replay-jumps button').last).to_be_focused()
        page.keyboard.press('Tab')
        expect(close).to_be_focused()
        smoke.check(True, 'replay focus wraps in both directions')
        radar = page.locator('.replay-radar')
        bounds = radar.bounding_box()
        smoke.check(bounds is not None and abs(bounds['width'] - bounds['height']) < 1 and bounds['y'] + bounds['height'] <= 900,
                    'replay radar is square and fits the desktop viewport')
        wp_bounds = page.locator('.replay-wp svg').bounding_box()
        expect(page.locator('.replay-control')).to_contain_text('T 控图')
        smoke.check(page.locator('.replay-control path').get_attribute('d').startswith('M'), 'replay renders the thin control series below WP')
        dialog_bounds = page.locator('.round-replay').bounding_box()
        smoke.check(wp_bounds is not None and dialog_bounds is not None and wp_bounds['y'] + wp_bounds['height'] < dialog_bounds['y'] + dialog_bounds['height'] <= 900,
                    'the entire WP chart fits in the modal at 1440x900')
        smoke.check(page.locator('.replay-player-abbr').count() == 10, 'every living dot has a short player name')
        expect(page.locator('.replay-clock')).to_contain_text('1:55')
        smoke.check(page.locator('.replay-anchors').count() == 0 and page.locator('.replay-wp [role=button]').count() == 3,
                    'one set of kill, smoke and plant markers replaces the duplicate track')
        smoke.check(page.locator('.replay-wp-marker text').all_text_contents() == ['☁', '💣', '×'], 'WP markers use the legend symbols')
        smoke.check(page.locator('.replay-wp-marker text').evaluate_all('rows => rows.every(el => Math.abs(Number(el.getAttribute("y")) - (65 - (.5 + Number(el.parentElement.dataset.time) * .05) * 60)) < .01)'),
                    'event symbols sit on the interpolated probability curve')
        smoke.check(page.locator('.replay-player-abbr').evaluate_all('rows => rows.slice(0, 5).every((a, i, group) => group.slice(i + 1).every(b => Math.abs(a.getBoundingClientRect().y - b.getBoundingClientRect().y) >= 9.8))'),
                    'five coincident spawn names stagger at least ten screen pixels')
        smoke.check(page.locator('.replay-player-name').count() == 0, 'replay does not label every player')
        # The first five dots deliberately share a spawn position; use an isolated
        # CT dot for pointer hit-testing after checking the staggered labels.
        dot = page.locator('.replay-player').nth(5)
        diameter = dot.evaluate('el => el.r.baseVal.value * el.getScreenCTM().a * 2')
        smoke.check(8 <= diameter <= 10 and dot.evaluate('el => getComputedStyle(el).strokeWidth') == '1px',
                    'replay dots are 8–10px with a 1px outline')
        dot.hover()
        expect(page.locator('.replay-player-name')).to_have_count(1)
        dot.click()
        page.mouse.move(0, 0)
        expect(page.locator('.replay-player-name')).to_have_count(1)
        scrubber.focus()
        page.keyboard.press('ArrowRight')
        expect(scrubber).to_have_value('3')
        page.keyboard.press('ArrowLeft')
        expect(scrubber).to_have_value('0')
        page.keyboard.press('ArrowLeft')
        expect(scrubber).to_have_value('0')
        page.keyboard.press('Space')
        expect(page.get_by_role('button', name='暂停', exact=True)).to_be_visible()
        page.keyboard.press('Space')
        expect(page.get_by_role('button', name='播放', exact=True)).to_be_visible()
        smoke.check(True, 'Space toggles playback and arrow keys seek three seconds with bounds')
        scrubber.fill('5')
        smoke.check(page.locator('.replay-player').count() == 9 and page.locator('.replay-kill').count() == 1,
                    'scrubbing applies the exact kill time and removes the victim')
        smoke.check(page.locator('.replay-plant').count() == 1, 'scrubbing reveals the plant')
        expect(page.locator('.replay-clock')).to_contain_text('0:39')
        expect(page.locator('.replay-killfeed')).to_contain_text('AK-47')
        smoke.check('ak47' not in page.locator('.replay-killfeed').inner_text(), 'kill feed shows readable weapon names, not demo ids')
        expect(page.locator('.replay-killfeed')).to_contain_text('爆头')
        expect(page.locator('.replay-killfeed')).to_contain_text('0:39 [T] Player 0 击杀 Player 9（爆头）（胜率 +12.5%）')
        expect(page.locator('.replay-events [data-kind=smoke]')).to_contain_text('1:52 [T] Player 0 投掷 VIP烟')
        expect(page.locator('.replay-events [data-kind=plant]')).to_contain_text('0:40 [T] — 在 A 点下包')
        expect(page.locator('.replay-events [data-kind=flash]')).to_have_count(0)
        page.get_by_role('checkbox', name='全部事件（含闪光）').check()
        expect(page.locator('.replay-events [data-kind=flash]')).to_contain_text('1:53 [CT] Player 6 投掷 闪光弹')
        page.get_by_role('checkbox', name='全部事件（含闪光）').uncheck()
        expect(page.locator('.replay-events [data-kind=flash]')).to_have_count(0)
        smoke.check(page.locator('.replay-kill-line').count() == 1 and page.locator('.replay-effect-smoke').count() == 1,
                    'kill line flashes for 1.5 seconds while smoke remains active')
        scrubber.fill('7')
        smoke.check(page.locator('.replay-kill-line').count() == 0 and page.locator('.replay-kill').count() == 1,
                    'kill line expires but death spot remains')
        scrubber.fill('0')
        page.keyboard.press('k')
        expect(scrubber).to_have_value('5')
        page.keyboard.press('p')
        expect(scrubber).to_have_value('4')
        page.keyboard.press('g')
        expect(scrubber).to_have_value('10')  # recipe median 35 clamps to duration 10
        page.locator('.replay-wp-marker[data-kind=util]').click()
        expect(scrubber).to_have_value('3')
        page.locator('.replay-wp [role=button]').first.focus()
        page.keyboard.press('Enter')
        expect(scrubber).to_have_value('3')
        smoke.check(True, 'K/P/G and keyboard event anchors seek and pause')
        page.get_by_role('button', name='4×', exact=True).click()
        expect(page.get_by_role('button', name='4×', exact=True)).to_have_attribute('aria-pressed', 'true')
        smoke.check('replay=' in page.url, 'recipe replay is represented in the URL')
        page.go_back()
        expect(page.locator('dialog[open]')).to_have_count(0)
        page.go_forward()
        page.wait_for_selector('dialog[open] .replay-radar')
        page.keyboard.press('Escape')
        expect(page.locator('dialog[open]')).to_have_count(0)
        selected.locator('.replay-open').click()
        page.wait_for_selector('dialog[open] .replay-radar')
        page.locator('.replay-close').click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(opener).to_be_focused()
        smoke.check(page.evaluate('document.body.style.overflow') == overflow, 'replay restores body scrolling and opener focus')
        smoke.check('replay=' not in page.url, 'Back, Escape and close remove the replay overlay')
    finally:
        page.unroute_all(behavior='ignoreErrors')
        page.emulate_media(reduced_motion='no-preference')


@route('#/de_mirage/tactics', '.tactics-page')
def check_replay_switching(smoke: Smoke, page: Page) -> None:
    """An obsolete response and playback state must not replace the selected round."""
    # G prefers the selected recipe's median (covered in check_tactics_linking).
    # Explicitly omit it here so this case exercises the first-entry-kill fallback.
    root = Path(__file__).resolve().parents[1]
    tactics_url = '**/data/de_mirage/tactics.json'
    tactics = json.loads((root / 'public/data/de_mirage/tactics.json').read_text())
    for recipe in tactics['recipes']:
        recipe.pop('median_commit_s', None)
    pending = []
    late_url = '**/data/de_mirage/replay/smoke-late/1.json'
    fast_url = '**/data/de_mirage/replay/smoke-fast/*.json'
    try:
        mock_json(page, tactics_url, tactics)
        page.route(late_url, lambda request: pending.append(request))
        page.route(fast_url, lambda request: request.fulfill(json={
            **replay_fixture(), 'demo_id': 'smoke-fast',
            'round_num': int(request.request.url.rsplit('/', 1)[1].split('.')[0]),
        }))
        page.emulate_media(reduced_motion='reduce')
        # Reload clears the application's cached tactics from the runner's initial visit.
        page.reload()
        # samples/site has no recipes. Page readiness must also work for that
        # valid empty state; populated exports still exercise missing medians.
        page.wait_for_selector('.tactics-page')
        with page.expect_request('**/data/de_mirage/replay/smoke-late/1.json'):
            page.goto(f'{smoke.base}/#/de_mirage/tactics?replay=smoke-late:1')
        page.wait_for_selector('dialog[open]')
        page.evaluate("location.hash = '/de_mirage/tactics?replay=smoke-fast:2'")
        expect(page.locator('.replay-title-match')).to_contain_text('第 2 回合')
        pending.pop().fulfill(json=replay_fixture())
        page.wait_for_timeout(100)
        expect(page.locator('.replay-title-match')).to_contain_text('第 2 回合')
        smoke.check(True, 'late replay response cannot replace the selected round')
        page.keyboard.press('g')
        expect(page.locator('.replay-scrubber')).to_have_value('5')
        smoke.check(True, 'G falls back to the first entry kill when no recipe commit time is available')
        page.locator('.replay-scrubber').fill('3')
        page.get_by_role('button', name='4×', exact=True).click()
        page.locator('.replay-player').first.focus()
        page.evaluate("location.hash = '/de_mirage/tactics?replay=smoke-fast:3'")
        expect(page.locator('.replay-title-match')).to_contain_text('第 3 回合')
        expect(page.locator('.replay-scrubber')).to_have_value('0')
        expect(page.get_by_role('button', name='1×', exact=True)).to_have_attribute('aria-pressed', 'true')
        expect(page.get_by_role('button', name='播放', exact=True)).to_be_visible()
        smoke.check(page.evaluate("document.querySelector('dialog').contains(document.activeElement)"),
                    'round switching resets time and speed and keeps focus in the modal')
        page.keyboard.press('Escape')
        expect(page.locator('dialog[open]')).to_have_count(0)
    finally:
        try:
            for request in pending:
                request.fulfill(json=replay_fixture())
        finally:
            page.unroute_all(behavior='ignoreErrors')
            page.emulate_media(reduced_motion='no-preference')


def replay_fixture() -> dict:
    return {
        'demo_id': 'smoke-replay', 'round_num': 1, 'map': 'de_mirage',
        'teams': {'T': 'Vitality', 'CT': 'B8'}, 'winner': 'T', 'duration': 10,
        'players': [{'name': f'Player {i}', 'side': 'T' if i < 5 else 'CT',
                     'team': 'Vitality' if i < 5 else 'B8'} for i in range(10)],
        'frames': [[[100 + second * 5, 300] if i < 5 else [100 + i * 50 + second * 5, 300 + i * 10] if i != 9 or second < 5 else None
                    for i in range(10)] for second in range(11)],
        'events': [{'t': 5, 'kind': 'kill', 'by': 0, 'victim': 9, 'at': [570, 390], 'weapon': 'ak47', 'headshot': True, 'wpa': .125},
                   {'t': 3, 'kind': 'util', 'nade': 'smoke', 'by': 0, 'at': [300, 300], 'from': [100, 300], 'side': 'T', 'place': 'VIP'},
                   {'t': 2, 'kind': 'util', 'nade': 'flash', 'by': 6, 'at': [450, 400], 'from': [400, 400]},
                   {'t': 4, 'kind': 'plant', 'site': 'A', 'at': [560, 760]}],
        'wp_t': [.5 + i * .05 for i in range(11)],
        't_control': [.4 + i * .02 for i in range(11)],
    }


@route('#/teams-hub?team=vitality', '.hub-orbit-node')
def check_hub_samples(smoke: Smoke, page: Page) -> None:
    """Exercise a changed reliability threshold and stale team-wide totals."""
    overview = page.request.get(f'{smoke.base}/data/index.json').json()
    teams = page.request.get(f'{smoke.base}/data/heatmap_teams.json').json()
    team = next(t for t in teams if t['slug'] == 'vitality')
    team['maps'] = [m for m in team['maps'] if m['map'] != 'de_cache']
    # Keep n_matches stale on purpose: the subtitle must sum the rendered nodes.
    team['n_matches'] = 9999
    overview['min_matches_reliable'] = max(m['n_matches'] for m in team['maps']) + 1
    try:
        mock_json(page, '**/data/index.json', overview)
        mock_json(page, '**/data/heatmap_teams.json', teams)
        page.reload()
        cache = page.locator('#hub-map-de_cache')
        expect(cache).to_have_attribute('aria-disabled', 'true')
        expect(cache).to_contain_text('暂无数据')
        before = page.url
        cache.click(force=True)
        cache.focus()
        page.keyboard.press('Enter')
        smoke.check(page.url == before, 'zero-Cache team keeps the dashed disabled node')
        expect(page.locator('.hub-map-badge')).to_have_count(0)
        expect(page.locator('.low-sample-chip')).to_have_count(sum(m['n_matches'] > 0 for m in team['maps'] if m['map'] in [
            'de_dust2', 'de_mirage', 'de_ancient', 'de_anubis', 'de_inferno', 'de_nuke']))
        page.mouse.move(0, 0)
        page.evaluate('document.activeElement.blur()')
        total = sum(m['n_matches'] for m in team['maps'] if m['map'] in [
            'de_dust2', 'de_mirage', 'de_ancient', 'de_anubis', 'de_inferno', 'de_nuke'])
        expect(page.locator('.hub-orbit-hud')).to_contain_text(f'{total} 场地图比赛 · 7 张图池')
        smoke.check(True, 'index threshold changes hide all unreliable badges and stale team totals cannot affect the subtitle')
    finally:
        page.unroute('**/data/index.json')
        page.unroute('**/data/heatmap_teams.json')


@route('#/', '.map-grid')
def check_cache_pages(smoke: Smoke, page: Page) -> None:
    overview = page.request.get(f'{smoke.base}/data/index.json').json()
    available = any(m['map'] == 'de_cache' and m['n_matches'] > 0 for m in overview['maps'])
    check_home(smoke, page)
    if available:
        for path, ready in [('tactics', '.tactics-page'), ('lineups', '.lineup-card'), ('players', '.player-card')]:
            page.goto(f'{smoke.base}/#/de_cache/{path}')
            page.wait_for_selector(ready)
            smoke.check(True, f'Cache {path} route renders exported data')
        replay_index = page.request.get(f'{smoke.base}/data/de_cache/replay/index.json').json()
        demo, rounds = next(iter(replay_index.items()))
        page.emulate_media(reduced_motion='reduce')
        page.goto(f'{smoke.base}/#/de_cache/tactics?replay={demo}:{rounds[0]}')
        page.wait_for_selector('dialog[open] .replay-radar')
        smoke.check(page.locator('.replay-radar image').get_attribute('href').endswith('radars/de_cache.png'),
                    'Cache replay uses the calibrated map radar asset')
        smoke.check(page.locator('.replay-player').count() > 0, 'Cache replay loads live positions on its radar')
        page.keyboard.press('Escape')
        page.goto(f'{smoke.base}/#/teams-hub?team=vitality&map=de_cache')
        page.wait_for_selector('.hub-player-card')
        page.locator('.hub-player-card').first.click()
        page.wait_for_selector('.hub-player-view')
        smoke.check('map=de_cache' in page.url and 'player=' in page.url, 'Cache player detail opens from its map overview')
    # A data-free deployment must not offer a Cache home link either.
    overview['maps'] = [m for m in overview['maps'] if m['map'] != 'de_cache']
    try:
        mock_json(page, '**/data/index.json', overview)
        page.goto(f'{smoke.base}/#/')
        page.reload()
        cache = page.locator('.map-card').filter(has_text='Cache')
        expect(cache.locator('.map-no-data')).to_have_text('暂无数据')
        expect(cache.locator('a')).to_have_count(0)
        expect(cache.locator('.map-card-radar')).to_have_count(0)
        smoke.check(True, 'home Cache availability follows the exported sample count')
    finally:
        page.unroute('**/data/index.json')
        page.emulate_media(reduced_motion='no-preference')


@route('#/teams-hub?team=vitality&map=de_mirage', '.hub-player-card')
def check_archive_replay(smoke: Smoke, page: Page) -> None:
    root = Path(__file__).resolve().parents[1]
    team = json.loads((root / 'public/data/de_mirage/teams/vitality.json').read_text())
    demo = team['matches'][0]['demo_id']
    team['matches'][0]['winprob_available'] = True
    try:
        mock_json(page, '**/data/de_mirage/teams/vitality.json', team)
        mock_json(page, f'**/data/de_mirage/winprob/{demo}.json', {
            'demo_id': demo, 'wp_t': {'1': [.5, .8], '2': [.5, .2]}, 'team_sides': {'vitality': {'1': 'T', '2': 'T'}}
        })
        mock_json(page, '**/data/de_mirage/replay/index.json', {demo: [1]})
        mock_json(page, f'**/data/de_mirage/replay/{demo}/1.json', {**replay_fixture(), 'demo_id': demo})
        page.reload()
        page.wait_for_selector('.hub-player-card')
        page.locator('.hub-team-matches > summary').click()
        row = page.locator(f'[id="match-{demo}"]')
        button = row.locator('.winprob-round[role="button"]')
        expect(button).to_have_count(1)
        smoke.check(row.locator('.winprob-round[role="img"]').count() == 1, 'rounds absent from the replay index remain static')
        smoke.check(row.locator('.winprob-round[role="img"][tabindex]').count() == 0, 'static rounds are not Tab stops')
        button.focus()
        page.keyboard.press('Enter')
        page.wait_for_selector('dialog[open] .replay-radar')
        page.keyboard.press('Escape')
        expect(page.locator('dialog[open]')).to_have_count(0)
        smoke.check('map=de_mirage' in page.url and 'team=vitality' in page.url,
                    'closing the archive replay preserves the hub map slide')
    finally:
        page.unroute_all(behavior='ignoreErrors')


@route('#/heatmaps/vitality?map=de_mirage', '.hm-player-card')
def check_heatmap_linking(smoke: Smoke, page: Page) -> None:
    # The first render canonicalizes defaults into the URL. Wait for that render
    # before focusing: MapLinkProvider deliberately invalidates links on URL changes.
    page.wait_for_function("""() => {
        const query = new URLSearchParams(location.hash.split('?')[1]);
        return ['side', 'players', 'view', 'phases', 'mode', 'sigma', 'level'].every(key => query.has(key));
    }""")
    # HashRouter may publish history before committing React. A reload at the
    # canonical URL makes those defaults the initial scope, with no pending rewrite.
    page.reload()
    page.wait_for_selector('.hm-player-card')
    # Keep auto-scrolling focused rows from putting another marker under the pointer.
    page.mouse.move(0, 0)
    keys = page.locator('.hm-player-card [data-map-link^="place:"]').evaluate_all(
        'rows => [...new Set(rows.map(row => row.dataset.mapLink))]')
    key = next(key for key in keys if page.locator(f'.hm-radar [data-map-link="{key}"]').count())
    row = page.locator(f'.hm-player-card [data-map-link="{key}"]').first
    marker = page.locator(f'.hm-radar [data-map-link="{key}"]').first
    row.focus()
    expect(row).to_be_focused()
    expect(marker).to_have_attribute('data-map-state', 'active')
    marker.focus()
    expect(marker).to_be_focused()
    expect(row).to_have_attribute('data-map-state', 'active')
    smoke.check(page.locator('.map-link-hint').count() == 1, 'heatmaps has one shared hover hint')
    smoke.check(page.locator('a[href*="teams-hub"][href*="team=vitality"]').count() == 1,
                'heatmap team navigation points to the merged hub')


@route('#/teams-hub', '.hub-team-card')
def check_teams_hub(smoke: Smoke, page: Page) -> None:
    page.locator('#hub-team-vitality').focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('#hub-map-de_mirage')
    smoke.check('team=vitality' in page.url, 'hub team selection is in URL')
    teams = page.request.get(f'{smoke.base}/data/heatmap_teams.json').json()
    mirage = next(m for t in teams if t['slug'] == 'vitality' for m in t['maps'] if m['map'] == 'de_mirage')
    smoke.check(page.locator('#hub-map-de_mirage strong .sr-only').inner_text() == f"{int(mirage['map_win_rate'] * 100 + .5)}%",
                'Vitality map card shows map wins, not round wins')
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-map-card .hub-count')].every(
        el => el.dataset.rolling === 'false' && el.querySelector('.sr-only').textContent === el.querySelector('.hub-number-final').textContent)""")
    smoke.check(True, 'animated map rates settle on the exact exported values')
    # A rotating card never passes Playwright's stability wait; dispatch the click.
    page.locator('#hub-map-de_mirage').dispatch_event('click')
    page.wait_for_selector('.hub-player-card')
    # The hub cross-fades whole scenes (teamsHubRoute.ts); there is no slide direction.
    smoke.check(page.locator('.hub-orbit').count() == 0 and page.locator('.hub-stage').count() == 1,
                'entering a map replaces the orbit scene')
    # Players beyond the five most-played sit in a collapsed "other players" drawer.
    smoke.check(page.locator('.hub-roster > .hub-player-cards > .hub-player-card').count() == 5,
                'map shows five portrait buttons')
    steamid = page.locator('.hub-player-card').first.get_attribute('id').removeprefix('hub-player-')
    portrait_line = page.locator('.hub-player-card .hub-portrait-line').first.inner_text()
    portrait_kpr = portrait_line.split('T 方每回合 ', 1)[1].split(' 杀', 1)[0]
    page.locator('.hub-player-card').first.focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-player-view')
    expect(page.locator('.hub-analysis-toolbar .hub-kpis .stat').first.locator('.sr-only')).to_have_text(portrait_kpr)
    smoke.check(True, 'portrait T-side KPR matches the player-page heatmap KPR')
    smoke.check(f'player={steamid}' in page.url and 'map=de_mirage' in page.url,
                'player and map selections are deep linked')
    quotes = page.request.get(f'{smoke.base}/data/player_quotes.json').json()
    quote = quotes.get(steamid) or {}
    has_verse = bool((quote.get('zh') or '').strip() or (quote.get('en') or '').strip())
    smoke.check(page.locator('.hub-verse').count() == int(has_verse),
                'owner verse is shown' if has_verse else 'absent owner verse is hidden')
    page.get_by_role('button', name='CT', exact=True).click()
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('side') === 'CT'")
    # HashRouter updates history before its deferred React render commits.
    expect(page.get_by_role('button', name='CT', exact=True)).to_have_attribute('aria-pressed', 'true')
    smoke.check(page.get_by_role('button', name='CT', exact=True).get_attribute('aria-pressed') == 'true',
                'CT segment changes selected state and URL')
    page.go_back()
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('side') === 'T'")
    expect(page.get_by_role('button', name='CT', exact=True)).to_have_attribute('aria-pressed', 'false')
    smoke.check(page.get_by_role('button', name='CT', exact=True).get_attribute('aria-pressed') == 'false',
                'Back restores default T side')
    page.go_forward()
    page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('side') === 'CT'")
    page.reload()
    page.wait_for_selector('.hub-player-view')
    smoke.check(page.get_by_role('button', name='CT', exact=True).get_attribute('aria-pressed') == 'true',
                'reload restores player and side')
    page.keyboard.press('Escape')
    page.wait_for_selector('.hub-player-card')
    smoke.check(page.locator('.hub-player-view').count() == 0, 'closing a player returns to the map scene')
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
    teams = page.request.get(f'{smoke.base}/data/heatmap_teams.json').json()
    results = sum(len(m.get('results') or []) for t in teams if t['slug'] == 'vitality' for m in t['maps'])
    smoke.check(page.locator('.hub-results li').count() == results, f'team panel lists every recorded result ({results})')
    card = page.locator('#hub-map-de_mirage')
    # The orbit rotates: hover the card where it is now instead of waiting for it to settle,
    # after the engine has painted for the current viewport (the layout check resizes it).
    wait_orbit_painted(page)
    card.hover(position={'x': 24, 'y': 28}, force=True)
    expect(card).to_have_attribute('data-active', 'true')
    # Without an owner photo the card shows the radar, brightened on hover; a photo replaces it.
    page.wait_for_load_state('networkidle')
    if card.locator('.card-scenic-bg').count() == 0:
        page.wait_for_function("""() => {
            const el = document.querySelector('#hub-map-de_mirage .map-card-bg');
            return !!el && parseFloat(getComputedStyle(el).opacity) > .3;
        }""")
        smoke.check('radars/de_mirage.png' in card.locator('.map-card-bg').evaluate('el => getComputedStyle(el).backgroundImage'),
                    'hover previews the selected map radar')
    else:
        smoke.check(card.locator('.map-card-bg').count() == 0, 'an owner photo replaces the radar preview')
    expect(page.locator('.hub-orbit-preview')).to_contain_text('T 胜率')
    expect(page.locator('.hub-orbit-preview')).to_contain_text('CT 胜率')
    expect(page.locator('.hub-orbit-preview')).to_contain_text('招牌：')
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("getComputedStyle(document.querySelector('.hub-orbit-ring.is-outer')).animationName === 'none'")
    smoke.check(card.evaluate("el => getComputedStyle(el).transform") == 'none',
                'reduced motion stops orbit rotation and node tilt while preserving placement')
    page.emulate_media(reduced_motion='no-preference')


def wait_orbit_painted(page: Page) -> None:
    """Wait until the orbit engine has painted for the current stage size (it sets the rays' viewBox)."""
    page.wait_for_function("""() => {
        const stage = document.querySelector('.hub-orbit'), rays = stage?.querySelector('.hub-orbit-rays');
        return !!rays && rays.getAttribute('viewBox') === `0 0 ${stage.clientWidth} ${stage.clientHeight}`;
    }""", polling=50)


def check_orbit_geometry(smoke: Smoke, page: Page, label: str) -> None:
    page.evaluate('document.fonts.ready.then(() => undefined)')
    page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    # Under page.clock the double rAF above is a timer, not a rendered frame.
    wait_orbit_painted(page)
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-orbit-node')].every(
        el => !el.getAnimations().some(a => a.playState === 'running' || a.pending))""")
    report = page.evaluate("""() => {
        const box = el => {
            const r = el.getBoundingClientRect();
            return Object.fromEntries(['left', 'right', 'top', 'bottom', 'width', 'height'].map(k => [k, r[k]]));
        };
        const stage = box(document.querySelector('.hub-orbit'));
        const intro = box(document.querySelector('.hub-orbit-intro'));
        const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
        const orbitActive = document.querySelector('.hub-orbit').hasAttribute('data-active');
        const emphasisOf = el => reducedMotion || el.dataset.empty === 'true' ? 1 : el.dataset.active === 'true' ? 1.08 : orbitActive ? .96 : 1;
        const nodes = [...document.querySelectorAll('.hub-orbit-node')].map(el => ({id: el.id, ...box(el)}));
        // The 10px spacing contract (orbit_geometry.mjs) is for fitted positions at depth scale;
        // the 1.08 hover/focus emphasis is transient, so spacing is measured without it.
        const fitted = nodes.map(a => {
            const e = emphasisOf(document.getElementById(a.id)), cx = (a.left + a.right) / 2, cy = (a.top + a.bottom) / 2;
            return {id: a.id, left: cx - a.width / e / 2, right: cx + a.width / e / 2, top: cy - a.height / e / 2, bottom: cy + a.height / e / 2};
        });
        const intersections = [], gaps = [], outside = [], viewportOutside = [], contentOutside = [], styles = [];
        for (const [i, a] of nodes.entries()) {
            if (a.left < stage.left || a.right > stage.right || a.top < stage.top || a.bottom > stage.bottom) outside.push(a.id);
            if (a.left < 0 || a.right > innerWidth || a.top < 0 || a.bottom > innerHeight) viewportOutside.push(a.id);
            const node = document.getElementById(a.id);
            for (const child of node.querySelectorAll('.hub-map-name, .hub-map-badge, .hub-rate, .hub-side-rate-bar, .hub-rate-label, small, .low-sample-chip')) {
                const r = child.getBoundingClientRect();
                if (r.bottom > a.bottom + 1 || r.top < a.top - 1 || r.left < a.left - 1 || r.right > a.right + 1) contentOutside.push(a.id);
            }
            for (const [j, b] of nodes.entries()) {
                if (j <= i) continue;
                const overlap = Math.max(b.left - a.right, a.left - b.right, b.top - a.bottom, a.top - b.bottom);
                if (overlap < 0) intersections.push([a.id, b.id]);
                // The fitted layout guarantees 10px (orbit_geometry.mjs); allow subpixel rounding.
                const fa = fitted[i], fb = fitted[j];
                const gap = Math.max(fb.left - fa.right, fa.left - fb.right, fb.top - fa.bottom, fa.top - fb.bottom);
                if (gap < 9.5) gaps.push({pair: [a.id, b.id], gap});
            }
            const el = document.getElementById(a.id), css = getComputedStyle(el);
            const emphasis = emphasisOf(el);
            const expectedScale = Number(css.getPropertyValue('--orbit-depth')) * emphasis;
            if (el.offsetWidth !== 196 || el.offsetHeight !== 252 || css.position !== 'absolute' || css.transform !== 'none' || css.translate !== '-50% -50%' || Math.abs(Number(css.scale) - expectedScale) > .005 ||
                (el.dataset.empty === 'true' && css.borderTopStyle !== 'dashed')) styles.push({id: a.id, position: css.position, transform: css.transform, translate: css.translate, scale: css.scale});
        }
        const coreEl = document.querySelector('.hub-orbit-core'), core = box(coreEl);
        const title = coreEl.querySelector('h2');
        const badge = box(coreEl.querySelector('.particle-logo')), name = box(title);
        const hud = box(coreEl.querySelector('.hub-orbit-hud'));
        const inspector = box(document.querySelector('.hub-orbit-inspector'));
        // Same 10px contract as web/e2e/orbit_geometry.mjs, less subpixel rounding; an
        // emphasised card may still not touch the core.
        const coreOverlaps = nodes.filter((a, i) => Math.max(core.left - fitted[i].right, fitted[i].left - core.right,
            core.top - fitted[i].bottom, fitted[i].top - core.bottom) < 9.5 ||
            Math.max(core.left - a.right, a.left - core.right, core.top - a.bottom, a.top - core.bottom) < 0).map(a => a.id);
        // Long team names are scaled to one line inside the core instead of wrapping under cards.
        const range = document.createRange(); range.selectNodeContents(title);
        const titleLines = new Set([...range.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top))).size;
        const titleFits = titleLines === 1 && name.left >= core.left - 1 && name.right <= core.right + 1 &&
            parseFloat(getComputedStyle(title).fontSize) >= (title.textContent.length <= 9 ? 32 : 16);
        const minimumCardWidth = innerWidth === 1440 ? 119 : innerWidth === 1280 ? 87 : 0;
        const undersized = nodes.filter(a => a.width < minimumCardWidth *
            (document.querySelector('.hub-orbit').hasAttribute('data-active') ? .96 : 1)).map(a => a.id);
        const rays = [...document.querySelectorAll('.hub-orbit-rays g > line:first-child')];
        const breadcrumbs = box(document.querySelector('.hub-breadcrumbs')), topbar = box(document.querySelector('.topbar'));
        const rayAligned = rays.every((line, i) => Math.abs(line.x2.baseVal.value - (nodes[i].left + nodes[i].width / 2 - stage.left)) < 1 && Math.abs(line.y2.baseVal.value - (nodes[i].top + nodes[i].height / 2 - stage.top)) < 1);
        return {bottomClearance: stage.bottom - Math.max(...nodes.map(n => n.bottom)), resultsToggle: box(document.querySelector('.hub-results-toggle')), previewBelow: inspector.top >= stage.bottom - 1, coreOverlaps, undersized, scrollY, breadcrumbs, topbar, rayAligned, breadcrumbVisible: breadcrumbs.top >= topbar.bottom && breadcrumbs.bottom <= innerHeight, nodes, stage, intersections, gaps, outside, viewportOutside, contentOutside, styles,
            introGap: Math.min(...nodes.map(n => n.top)) - intro.bottom,
            stacked: badge.bottom <= name.top + 1 && name.bottom <= hud.top + 1 && Math.abs(badge.height - 206) <= 1 && titleFits && Math.abs(core.width - 230) <= 1 && Math.abs(core.height - 285) <= 1 && hud.bottom <= core.bottom + 1 && [badge, name, hud].every(r => Math.abs((r.left + r.right) / 2 - (core.left + core.right) / 2) <= 1),
            // Card text keeps >= 11 screen px at the smallest rendered depth (F9).
            smallText: [...document.querySelectorAll('.hub-orbit-node')].flatMap(node => {
                const scale = Number(getComputedStyle(node).scale) || 1;
                return [...node.querySelectorAll('.hub-map-name, .hub-rate strong, .hub-rate-label, :scope > small, .hub-map-badge')]
                    .map(el => ({id: node.id, cls: el.className, px: parseFloat(getComputedStyle(el).fontSize) * scale}))
                    .filter(row => innerWidth >= 900 && row.px < 11);
            }),
            transparent: [coreEl, coreEl.parentElement, coreEl.querySelector('.hub-team-anchor'), coreEl.querySelector('.hub-orbit-hud')].every(el => {
                const css = getComputedStyle(el);
                return css.backgroundImage === 'none' && css.backgroundColor === 'rgba(0, 0, 0, 0)' &&
                    css.backdropFilter === 'none' && css.boxShadow === 'none' &&
                    ['Top', 'Right', 'Bottom', 'Left'].every(side => css[`border${side}Width`] === '0px');
            }),
            shielded:
                rays.every(line => Math.hypot(line.x1.baseVal.value - stage.width / 2, line.y1.baseVal.value - stage.height / 2) >= 119),
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth};
    }""")
    diagnostics = json.dumps(report, ensure_ascii=False)
    valid = (not any(report[key] for key in ('coreOverlaps', 'undersized', 'intersections', 'gaps', 'outside', 'viewportOutside', 'contentOutside', 'styles', 'smallText'))
             and report['bottomClearance'] >= 15.5 and report['introGap'] >= 16 and report['overflow'] <= 0
             and report['previewBelow'] and report['stacked'] and report['shielded'] and report['transparent'] and report['rayAligned'] and report['breadcrumbVisible'])
    if page.viewport_size == {'width': 1440, 'height': 900} and page.evaluate('scrollY') == 0:
        smoke.check(0 <= report['resultsToggle']['top'] and report['resultsToggle']['bottom'] <= 900, '1440x900: recent-results toggle stays visible in the first screen')
    smoke.check(valid, f'{label}: seven nodes fit with 10px gaps, >= 11px card text, aligned rays, visible breadcrumbs and transparent core'
                + (f': {diagnostics}' if not valid else ''))


def check_orbit_backdrops(smoke: Smoke, page: Page) -> None:
    manifest_pattern = '**/map-bg/manifest.json'
    mock_json(page, manifest_pattern, [])
    page.reload()
    expect(page.locator('.map-landmark-art')).to_have_count(7)
    smoke.check(page.locator('.map-landmark-art').evaluate_all("""els => els.every(el =>
        el.querySelectorAll('path').length >= 3 && el.querySelector('.landmark-building') &&
        getComputedStyle(el).position === 'absolute' &&
        Math.abs(parseFloat(getComputedStyle(el).height) - el.parentElement.clientHeight * .55) < 1 &&
        getComputedStyle(el).pointerEvents === 'none')"""),
        'all seven maps have original multi-layer landmark drawings and light rays')
    smoke.check(page.locator('.hub-orbit-node').evaluate_all("""els => els.every(el => {
        const strip = getComputedStyle(el, '::after');
        return strip.height === '2px' && strip.boxShadow === 'none';
    })"""), 'each map has a thin themed accent without a coloured glow')
    from io import BytesIO

    from PIL import Image
    image = BytesIO()
    Image.new('RGB', (480, 600), '#426050').save(image, 'WEBP')
    photo_pattern = '**/map-bg/*.webp'
    page.route(photo_pattern, lambda intercepted: intercepted.fulfill(body=image.getvalue(), content_type='image/webp'))
    page.unroute(manifest_pattern)
    mock_json(page, manifest_pattern, ['dust2', 'mirage', 'ancient', 'anubis', 'inferno', 'nuke', 'cache'])
    try:
        page.reload()
        expect(page.locator('.card-scenic-bg')).to_have_count(7)
        expect(page.locator('.map-card-bg')).to_have_count(0)
        smoke.check(page.locator('.card-scenic-bg').evaluate_all(r"""els => els.every(el =>
            getComputedStyle(el).opacity === '1' &&
            (getComputedStyle(el).filter === (el.parentElement.dataset.empty === 'true' ? 'grayscale(1) brightness(0.35)' : 'none')) &&
            getComputedStyle(el).maskImage === 'none' &&
            Math.abs(parseFloat(getComputedStyle(el).height) - el.parentElement.clientHeight * .55) < 1 &&
            (getComputedStyle(el.parentElement, '::before').backgroundImage.match(/rgba?\([^)]+\)/g) || []).every(colour => {
                const values = colour.match(/[\d.]+/g).map(Number);
                return values[3] === 0 || values.slice(0, 3).join(',') === '8,12,16';
            }) &&
            getComputedStyle(el.parentElement.querySelector('.map-landmark-art')).visibility === 'hidden')"""),
            'photos occupy 55%; empty maps alone are grayscale and darkened')
        # Staggered card entrances animate opacity; compare settled styles only.
        page.wait_for_function("""() => [...document.querySelectorAll('.hub-orbit-node, .hub-orbit-node *')].every(
            el => !el.getAnimations().some(a => a.playState === 'running' || a.pending))""")
        page.locator('#hub-map-de_mirage').focus()
        smoke.check(page.locator('.card-scenic-bg').evaluate_all('''els => els.every(el =>
            (getComputedStyle(el).filter === (el.parentElement.dataset.empty === 'true' ? 'grayscale(1) brightness(0.35)' : 'none')) && getComputedStyle(el).opacity === '1' &&
            getComputedStyle(el.parentElement).opacity === '1')'''),
            'focusing a card preserves grayscale empty maps and natural active photographs')
        page.unroute(photo_pattern)
        page.route(photo_pattern, lambda intercepted: intercepted.fulfill(body=b'not an image', content_type='image/webp'))
        page.reload()
        expect(page.locator('.card-scenic-probe')).to_have_count(0)
        expect(page.locator('.card-scenic-bg')).to_have_count(0)
        expect(page.locator('.map-landmark-art:visible')).to_have_count(7)
        smoke.check(True, 'failed photos leave all architectural fallbacks visible')
    finally:
        page.unroute(photo_pattern)
        page.unroute(manifest_pattern)
        page.reload()
        page.wait_for_selector('.hub-orbit-node')


@route('#/teams-hub?team=vitality', '.hub-orbit-node')
def check_hub_orbit_v4(smoke: Smoke, page: Page) -> None:
    """Exercise the live rAF engine at multiple phases, then motion/fallback states."""
    # Install the clock before mounting the engine; replacing a live clock can
    # orphan the already-scheduled native rAF and make phase 0 a false failure.
    page.clock.install()
    page.emulate_media(reduced_motion='no-preference')
    page.reload()
    page.mouse.move(0, 0)
    page.evaluate('document.activeElement.blur()')
    orbit = page.locator('.hub-orbit')
    expect(orbit).to_have_attribute('data-running', 'true')
    for width, height in [(1440, 900), (1280, 800)]:
        page.set_viewport_size({'width': width, 'height': height})
        # A resize re-observes the stage; sample only once the loop runs again.
        expect(orbit).to_have_attribute('data-running', 'true')
        for sample in range(7):
            before = float(orbit.get_attribute('data-phase') or 0)
            page.clock.run_for(4000)
            page.clock.resume()
            after = float(orbit.get_attribute('data-phase') or 0)
            smoke.check(abs(after - before) > .2, f'{width}x{height}: rAF advances phase {sample}')
            check_orbit_geometry(smoke, page, f'{width}x{height} moving phase {after:.2f}')
        card = page.locator('#hub-map-de_mirage')
        # A rotating card cannot satisfy Playwright's pre-hover stability wait.
        # Move onto its current position, then verify the engine brakes it.
        card.hover(force=True)
        page.clock.run_for(1800)
        page.clock.resume()
        expect(orbit).to_have_attribute('data-running', 'false')
        stopped = orbit.get_attribute('data-phase')
        page.clock.run_for(600)
        page.clock.resume()
        smoke.check(orbit.get_attribute('data-phase') == stopped, 'hover brakes to a stable phase')
        page.mouse.move(0, 0)
        page.clock.run_for(500)
        page.clock.resume()
        smoke.check(orbit.get_attribute('data-phase') != stopped, 'leaving resumes rotation')
        card.focus()
        page.keyboard.press('ArrowRight')
        expect(page.locator('#hub-map-de_ancient')).to_be_focused()
        page.clock.run_for(1800)
        page.clock.resume()
        expect(orbit).to_have_attribute('data-running', 'false')
        page.evaluate('document.activeElement.blur()')
        page.emulate_media(reduced_motion='reduce')
        expect(orbit).to_have_attribute('data-phase', '0')
        page.clock.run_for(1000)
        page.clock.resume()
        expect(orbit).to_have_attribute('data-phase', '0')
        check_orbit_geometry(smoke, page, f'{width}x{height} reduced-motion static')
        static_logo = page.locator('.particle-logo-static')
        expect(static_logo).to_have_css('opacity', '1')
        expect(page.locator('.particle-logo-canvas')).to_have_css('display', 'none')
        # Resizing while reduced motion is active must repaint the same fitted
        # geometry without waiting for an animation frame or React remount.
        other = (1280, 800) if width == 1440 else (1440, 900)
        page.set_viewport_size({'width': other[0], 'height': other[1]})
        check_orbit_geometry(smoke, page, f'{other[0]}x{other[1]} reduced-motion resize')
        expect(orbit).to_have_attribute('data-phase', '0')
        expect(orbit).to_have_attribute('data-running', 'false')
        page.set_viewport_size({'width': width, 'height': height})
        smoke.check(True, 'reduced motion preserves a static logo and fixed orbit across resize')
        page.emulate_media(reduced_motion='no-preference')

    # All installed team PNGs use the same sampler, independent of Falcons.
    assets = page.request.get(f'{smoke.base}/data/asset_slots.json').json()
    for slug in ('vitality', 'falcons', 'spirit'):
        if slug not in assets['teams']:
            continue
        page.goto(f'{smoke.base}/#/teams-hub?team={slug}')
        canvas = page.locator('.particle-logo-canvas')
        page.wait_for_function("""slug => {
            const el = document.querySelector('.particle-logo-canvas');
            return el?.dataset.samplingDone === 'true' &&
                el.dataset.sampledSource?.endsWith(`/logos/teams/${slug}.png`) &&
                Number(el.dataset.particleCount) > 120;
        }""", arg=slug)
        report = canvas.evaluate("""el => ({count: Number(el.dataset.particleCount), width: el.width,
            paused: el.dataset.paused, source: el.parentElement.querySelector('.particle-logo-static img').src})""")
        smoke.check(120 < report['count'] <= 2000 and report['width'] <= 440 and f'logos/teams/{slug}.png' in report['source'],
                    f'{slug}: bounded DPR-aware particles sample the actual team PNG')
        page.locator('.particle-logo').evaluate("el => el.style.transform = 'translateY(2000px)'")
        expect(canvas).to_have_attribute('data-paused', 'true')
        page.locator('.particle-logo').evaluate("el => el.style.transform = ''")
        expect(canvas).to_have_attribute('data-paused', 'false')
        page.evaluate("""() => {
            Object.defineProperty(document, 'hidden', {configurable: true, value: true});
            document.dispatchEvent(new Event('visibilitychange'));
        }""")
        expect(canvas).to_have_attribute('data-paused', 'true')
        expect(page.locator('.hub-orbit')).to_have_attribute('data-running', 'false')
        page.evaluate("""() => {
            delete document.hidden;
            document.dispatchEvent(new Event('visibilitychange'));
        }""")
        expect(canvas).to_have_attribute('data-paused', 'false')
        smoke.check(True, f'{slug}: hidden/offscreen particles pause and resume')
        expect(page.locator('.particle-logo-static')).to_have_css('opacity', '0.25')
        page.emulate_media(reduced_motion='reduce')
        expect(canvas).to_have_css('display', 'none')
        expect(page.locator('.particle-logo-static')).to_have_css('opacity', '1')
        page.emulate_media(reduced_motion='no-preference')
    # Missing assets must never leave an invisible core.
    mock_json(page, '**/data/asset_slots.json', {**assets, 'teams': []})
    page.reload()
    expect(page.locator('.particle-logo')).to_have_attribute('data-logo-source', 'shield')
    expect(page.locator('.particle-logo-static .team-shield')).to_have_count(1)
    page.emulate_media(reduced_motion='reduce')
    expect(page.locator('.particle-logo-canvas')).to_have_css('display', 'none')
    expect(page.locator('.particle-logo-static')).to_have_css('opacity', '1')
    page.emulate_media(reduced_motion='no-preference')
    smoke.check(True, 'missing PNG uses TeamShield and hides the canvas under reduced motion')
    page.unroute('**/data/asset_slots.json')
    if assets['teams']:
        slug = next((slug for slug in ('vitality', 'falcons') if slug in assets['teams']), assets['teams'][0])
        page.route('**/logos/teams/*.png', lambda intercepted: intercepted.fulfill(body=b'bad PNG', content_type='image/png'))
        page.goto(f'{smoke.base}/#/teams-hub?team={slug}')
        page.reload()
        expect(page.locator('.particle-logo')).to_have_attribute('data-logo-source', 'shield')
        expect(page.locator('.particle-logo-static .team-shield')).to_have_count(1)
        page.unroute('**/logos/teams/*.png')
        smoke.check(True, 'unreadable supplied PNG restores TeamShield')

    # Exercise both inclusive boundaries and low-sample colour independence.
    teams = page.request.get(f'{smoke.base}/data/heatmap_teams.json').json()
    team = next(t for t in teams if t['slug'] == 'vitality')
    rates = [(.4999, 'rgb(244, 63, 94)'), (.5, 'rgb(248, 250, 252)'),
             (.5999, 'rgb(248, 250, 252)'), (.6, 'rgb(34, 197, 94)'), (.65, 'rgb(34, 197, 94)')]
    for entry, (rate, _) in zip(team['maps'], rates):
        entry.update(map_win_rate=rate, n_matches=1)
    mock_json(page, '**/data/heatmap_teams.json', teams)
    page.goto(f'{smoke.base}/#/teams-hub?team=vitality')
    page.reload()
    for entry, (_, color) in zip(team['maps'], rates):
        expect(page.locator(f'#hub-map-{entry["map"]} .hub-arc')).to_have_css('stroke', color)
    smoke.check(True, 'absolute colours include 50% and 60% boundaries even below the badge sample threshold')
    page.unroute('**/data/heatmap_teams.json')


def wilson(rate: float, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = max(0.0, min(1.0, rate))
    z2 = z * z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z / (1 + z2 / n) * (p * (1 - p) / n + z2 / (4 * n * n)) ** .5
    return max(0.0, centre - half), min(1.0, centre + half)


def map_badges(maps: list[dict], min_matches: int | None) -> tuple[str | None, str | None]:
    """Mirror of mapBadges (src/pages/teamsHubOrbit.ts; unit tests in map_badges.mjs)."""
    if min_matches is None:
        return None, None
    threshold = max(8, min_matches)
    rows = [{'map': m['map'], 'rate': m['map_win_rate'], 'rounds': m.get('round_win_rate'),
             'bounds': wilson(m['map_win_rate'], m['n_matches'])}
            for m in maps if m['n_matches'] >= threshold and m.get('map_win_rate') is not None]
    if len(rows) < 2:
        return None, None

    def rounds(row: dict) -> float:
        return .5 if row['rounds'] is None else row['rounds']

    best = min(rows, key=lambda r: (-r['bounds'][0], -rounds(r), r['map']))
    worst = min(rows, key=lambda r: (r['bounds'][1], rounds(r), r['map']))
    margin = ((best['bounds'][1] - best['bounds'][0]) + (worst['bounds'][1] - worst['bounds'][0])) / 4
    if best['map'] == worst['map'] or best['rate'] <= worst['rate'] or worst['bounds'][1] - best['bounds'][0] > margin / 2:
        return None, None
    if best['rounds'] is not None and worst['rounds'] is not None and best['rounds'] < worst['rounds']:
        return None, None
    return best['map'], worst['map']


@route('#/teams-hub?team=vitality', '.hub-orbit-node')
def check_hub_orbit(smoke: Smoke, page: Page) -> None:
    pool = ['de_dust2', 'de_mirage', 'de_ancient', 'de_anubis', 'de_inferno', 'de_nuke', 'de_cache']
    nodes = page.locator('.hub-orbit-node')
    expect(nodes).to_have_count(7)
    smoke.check(nodes.evaluate_all('(els) => els.map(el => el.id)') == [f'hub-map-{m}' for m in pool],
                'orbit has seven nodes in stable clockwise pool order, including Cache')
    check_orbit_backdrops(smoke, page)
    overview = page.request.get(f'{smoke.base}/data/index.json').json()
    entries = page.request.get(f'{smoke.base}/data/heatmap_teams.json').json()
    team = next(t for t in entries if t['slug'] == 'vitality')
    shown = [m for m in team['maps'] if m['map'] in pool]
    count = sum(m['n_matches'] for m in shown)
    page.mouse.move(0, 0)
    page.evaluate('document.activeElement.blur()')
    expect(page.locator('.hub-orbit-hud')).to_contain_text(f'{count} 场地图比赛 · 7 张图池')
    best, worst = map_badges(shown, overview['min_matches_reliable'])
    for map_id in pool:
        entry = next((m for m in shown if m['map'] == map_id), None)
        node = page.locator(f'#hub-map-{map_id}')
        available = bool(entry and entry['n_matches'])
        expect(node).to_have_attribute('aria-disabled', str(not available).lower())
        expect(node.locator('.is-best')).to_have_count(int(available and map_id == best))
        expect(node.locator('.is-weak')).to_have_count(int(available and map_id == worst))
        if available:
            rate = entry.get('map_win_rate')
            category = 'neutral' if rate is None else 'strong' if rate >= .6 else 'neutral' if rate >= .5 else 'weak'
            expect(node).to_have_attribute('data-rate', category)
            color = {'strong': 'rgb(34, 197, 94)', 'neutral': 'rgb(248, 250, 252)', 'weak': 'rgb(244, 63, 94)'}[category]
            expect(node.locator('.hub-arc')).to_have_css('stroke', color)
            expect(node.locator('.hub-side-rate-bar')).to_have_count(1)
            expect(node.locator('.hub-side-rate-bar i')).to_have_count(2)
        if available and entry['n_matches'] < overview['min_matches_reliable']:
            chip = node.locator('.low-sample-chip')
            expect(chip).to_have_text('!')
            expect(chip).to_have_attribute('title', '样本不足，结果仅供参考。')
            expect(chip).to_have_attribute('aria-label', '样本不足，结果仅供参考。')
    smoke.check(True, 'badges use index minimum sample; low-sample notes are compact accessible chips; subtitle sums shown nodes')
    cache = page.locator('#hub-map-de_cache')
    before = page.url
    for node in page.locator('.hub-orbit-node[data-empty="true"]').all():
        expect(node).to_contain_text('暂无数据')
        node.click(force=True)
        node.focus()
        page.keyboard.press('Enter')
        smoke.check(page.url == before, f'{node.get_attribute("id")} has no data and cannot open')
    if cache.get_attribute('data-empty') == 'false':
        cache.focus()
        page.keyboard.press('Enter')
        page.wait_for_selector('.hub-player-card')
        smoke.check('map=de_cache' in page.url, 'Cache opens its real map overview and players')
        page.keyboard.press('Escape')
        expect(cache).to_be_focused()
    page.locator('#hub-map-de_dust2').focus()
    for map_id in pool[1:] + pool[:1]:
        page.keyboard.press('ArrowRight')
        expect(page.locator(f'#hub-map-{map_id}')).to_be_focused()
    page.keyboard.press('ArrowLeft')
    expect(cache).to_be_focused()
    smoke.check(True, 'left/right cycle through all seven nodes and wrap')
    page.locator('#hub-map-de_dust2').focus()
    for map_id in pool[1:]:
        page.keyboard.press('Tab')
        expect(page.locator(f'#hub-map-{map_id}')).to_be_focused()
    smoke.check(True, 'Tab follows clockwise orbit order, including placeholders')
    card = page.locator('#hub-map-de_mirage')
    for width, height in [(1440, 900), (1280, 800)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.mouse.move(0, 0)
        page.evaluate('document.activeElement.blur()')
        page.evaluate('scrollTo(0, 0)')
        check_orbit_geometry(smoke, page, f'{width}x{height} idle')
        if smoke.shots:
            page.screenshot(path=str(smoke.shots / f'vitality_orbit_{width}.png'))
        for node in nodes.all():
            node.focus()
            check_orbit_geometry(smoke, page, f'{width}x{height} focus {node.get_attribute("id")}')
            node.hover(position={'x': 12, 'y': 12})
            check_orbit_geometry(smoke, page, f'{width}x{height} hover {node.get_attribute("id")}')
            page.mouse.move(0, 0)
        details = page.locator('.hub-team-results')
        if not details.evaluate('el => el.open'):
            details.locator('summary').click()
        smoke.check(details.bounding_box()['y'] >= page.locator('.hub-orbit').bounding_box()['y'] + page.locator('.hub-orbit').bounding_box()['height'],
                    f'{width}x{height}: results drawer expands below the stage')
        expect(details.locator('.match-time-filter')).to_be_visible()
        details.locator('summary').click()
        page.evaluate('scrollTo(0, 0)')
    page.set_viewport_size({'width': 1440, 'height': 900})
    # The resize re-lays out the orbit; hover only after that paint, where the card is now
    # (the idle orbit rotates, so it never passes Playwright's stability wait).
    wait_orbit_painted(page)
    card.hover(position={'x': 24, 'y': 28}, force=True)
    expect(card).to_have_attribute('data-active', 'true')
    expect(page.locator('.hub-orbit-preview')).to_contain_text('T 胜率')
    expect(page.locator('.hub-orbit-preview')).to_contain_text('CT 胜率')
    page.wait_for_function("""() => {
        const text = document.querySelector('.hub-orbit-preview')?.textContent || '';
        return text.includes('招牌：') && !text.includes('读取中');
    }""")
    smoke.check(True, 'hover shows side rates and a nonblocking tactical preview')
    wraps = page.locator('.hub-orbit-preview > span').last.evaluate("""el => {
        const original = el.textContent;
        try {
            el.textContent = '招牌：连接烟 + 丛林烟 + 警家烟 + 拱门闪光 + 中路控制 + A 点同步进攻';
            const css = getComputedStyle(el), rect = el.getBoundingClientRect();
            const line = parseFloat(css.lineHeight);
            return css.whiteSpace === 'normal' && css.webkitLineClamp === '2' &&
                rect.height > line * 1.5 && rect.height <= line * 2 + 1 && el.scrollWidth <= el.clientWidth;
        } finally { el.textContent = original; }
    }""")
    smoke.check(wraps, 'signature preview wraps to two lines below the orbit')
    card.focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-player-card')
    expect(page.locator('.hub-stage')).to_have_css('view-transition-name', 'hub-scene')
    smoke.check('map=de_mirage' in page.url, 'Enter opens the focused map via HashRouter')
    page.keyboard.press('Escape')
    expect(card).to_be_focused()
    expect(card).to_have_attribute('data-active', 'true')
    for width, height in [(1440, 900), (1280, 800)]:
        page.set_viewport_size({'width': width, 'height': height})
        check_orbit_geometry(smoke, page, f'{width}x{height} after map return')
    smoke.check(True, 'Escape restores selected node focus and fully visible breadcrumbs')
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-player-card')
    page.go_back()
    expect(card).to_be_focused()
    page.go_forward()
    page.wait_for_selector('.hub-player-card')
    smoke.check('map=de_mirage' in page.url, 'Back/Forward restore orbit and map routes')
    page.keyboard.press('Escape')
    expect(card).to_be_focused()
    page.emulate_media(reduced_motion='reduce')
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-player-card')
    expect(page.locator('.hub-stage')).to_have_css('view-transition-name', 'none')
    page.keyboard.press('Escape')
    expect(card).to_be_focused()
    smoke.check(True, 'reduced motion swaps instantly and preserves return focus')
    page.emulate_media(reduced_motion='no-preference')
    page.evaluate('document.startViewTransition = undefined')
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-player-card')
    expect(page.locator('.hub-stage')).to_have_css('view-transition-name', 'hub-scene')
    page.keyboard.press('Escape')
    expect(card).to_be_focused()
    smoke.check(True, 'unsupported View Transitions API commits immediately with a 180ms opacity entrance')


@route('#/teams-hub?team=vitality&map=de_mirage', '.hub-player-card')
def check_hub_map(smoke: Smoke, page: Page) -> None:
    smoke.check(page.locator('.hub-map-context .hub-kpis .stat').count() == 4, 'map overview shows four leading metrics')
    profile = page.request.get(f'{smoke.base}/data/de_mirage/teams/vitality.json').json()
    archive = page.locator('.hub-team-matches')
    smoke.check(archive.get_attribute('open') is None, 'map match archive starts collapsed below the roster')
    # Rows can hold their own replay disclosures: address each card's own summary.
    archive.locator(':scope > summary').click()
    smoke.check(archive.locator('.match').count() == len(profile['matches']), 'map archive lists every exported match')
    outcomes = {row['demo_id']: 'W' if row['score_for'] > row['score_against'] else 'L' if row['score_for'] < row['score_against'] else 'D'
                for row in profile['matches']}
    first = archive.locator('.match').first
    smoke.check(first.locator('.match-outcome').inner_text() == outcomes[first.get_attribute('id').removeprefix('match-')],
                'match archive retains the outcome tag')
    basis = page.locator('.hub-team-basis')
    smoke.check(basis.get_attribute('open') is None, 'detailed stats and heatmap link start collapsed')
    basis.locator(':scope > summary').click()
    smoke.check(page.locator('.hub-archive-card').count() == 3, 'map archive has three summary cards')
    heatmap = page.locator('.hub-team-radar')
    heatmap.locator(':scope > summary').click()
    smoke.check(heatmap.locator('a[href*="heatmaps/vitality"]').count() == 1, 'heatmap summary card links to the heatmap tool')
    heatmap.locator(':scope > summary').click()
    basis.locator(':scope > summary').click()
    archive.locator(':scope > summary').click()


@route('#/teams-hub?team=vitality&map=de_mirage&player=76561198113666193&side=CT', '.hub-player-view')
def check_hub_player(smoke: Smoke, page: Page) -> None:
    smoke.check(page.locator('.hub-map-figure .hm-radar').count() == 1, 'deep-linked player has one primary radar')
    smoke.check(page.locator('.hub-player-bio').count() == 1, 'deep-linked player has portrait column')
    smoke.check(page.locator('.hub-analysis-toolbar .stat').count() == 3,
                'sample size is beside the title rather than a fourth stat card')
    smoke.check(page.locator('.hub-sample-inline').count() == 1, 'sample size is small title metadata')
    page.get_by_role('button', name='中期控图', exact=True).click()
    expect(page.locator('.hub-player-view')).to_have_attribute('data-phase', 'mid')
    page.get_by_role('button', name='下包后/残局', exact=True).click()
    expect(page.locator('.hub-player-view')).to_have_attribute('data-phase', 'post')
    page.get_by_role('button', name='开局', exact=True).click()
    expect(page.locator('.hub-player-view')).to_have_attribute('data-phase', 'early')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    overflow = page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
    smoke.check(overflow <= 0, '1920px player view has no horizontal overflow')
    page.set_viewport_size({'width': 1280, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-count')].every(
        el => el.dataset.rolling === 'false' && el.querySelector('.sr-only').textContent === el.querySelector('.hub-number-final').textContent)""")
    page.get_by_role('button', name='T', exact=True).click()
    page.wait_for_function("""() => document.querySelector('.hub-side-switch .segment-highlight') &&
        getComputedStyle(document.querySelector('.hub-side-switch .segment-highlight')).transitionDuration === '0s' &&
        !document.querySelector('.hub-stage').getAnimations({subtree: true}).some(a => a.playState === 'running')""")
    smoke.check(page.locator('.hub-stage').evaluate('(el) => getComputedStyle(el).animationName') == 'none',
                'reduced motion disables CSS motion and WAAPI count-ups during a side change')
    page.wait_for_function("""() => [...document.querySelectorAll('.hub-count')].every(
        el => el.dataset.rolling === 'false' && el.querySelector('.sr-only').textContent === el.querySelector('.hub-number-final').textContent)""")
    smoke.check(True, 'reduced motion presents final numeric values immediately')
    page.emulate_media(reduced_motion='no-preference')
    page.wait_for_function("getComputedStyle(document.querySelector('.hub-side-switch .segment-highlight')).transitionDuration !== '0s'")
    # Exercise interruption: a queued map exit must not override a newer team close.
    page.keyboard.press('Escape')
    page.keyboard.press('Escape')
    page.wait_for_selector('.hub-map-card')
    smoke.check('map=' not in page.url and 'player=' not in page.url,
                'rapid Escape follows current URL depth without stale transition completion')
    page.emulate_media(reduced_motion='no-preference')


@route('#/teams-hub?team=vitality&map=de_mirage&player=76561198113666193&side=all', '.hub-player-view')
def check_hub_entrance(smoke: Smoke, page: Page) -> None:
    # Entrance coverage must not inherit reduced motion from a failed previous case.
    page.emulate_media(reduced_motion='no-preference')
    # Test owner-style copy without modifying the sample registry or production data.
    player = '76561198113666193'
    smoke.check(page.locator('.hub-side-switch button').count() == 2, 'heatmap offers T and CT only')
    try:
        mock_json(page, '**/data/player_quotes.json', {
            player: {'name': 'ZywOo', 'zh': '一箫一剑平生意，负尽狂名十五年', 'en': ''}
        })
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
                    'full entrance settles with one complete accessible verse')
        verse = page.locator('.hub-verse-columns').inner_text()
        smoke.check(page.locator('.hub-verse-character').count() == 0, 'vertical verse has plain text columns without competing glyph transforms')
        for button in ['道具落点', '站位']:
            page.get_by_role('button', name=button, exact=True).click()
        smoke.check(page.locator('.hub-verse-columns').inner_text() == verse and page.locator('.hub-verse').evaluate('el => getComputedStyle(el).animationName') == 'none',
                    'layer rerenders preserve the verse and never restart its animation')
        smoke.check(page.locator('.hub-verse').evaluate('el => Number(getComputedStyle(el).opacity)') == 1, 'verse stays at full strength after the entrance')
        details = page.locator('.hub-player-analysis > details')
        smoke.check(details.evaluate("el => Boolean(el.querySelector('h3').compareDocumentPosition(el.querySelector('.hub-kpis')) & Node.DOCUMENT_POSITION_FOLLOWING)"),
                    'player details begin with a section heading before the large role statistics')
        ghost = page.get_by_role('checkbox', name='对比本图同阵营职业平均', exact=True)
        if not ghost.is_checked():
            ghost.click()
        expect(ghost).to_be_checked()
        expect(page.locator('.ghost-legend')).to_contain_text('琥珀色')
        page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('ghost') === '1'")
        smoke.check('ghost=1' in page.url and page.locator('.hub-layer-in image').count() > 0, 'ghost comparison is rendered and represented in the URL')
        ghost.uncheck()
        expect(ghost).not_to_be_checked()
        page.wait_for_function("!new URLSearchParams(location.hash.split('?')[1]).has('ghost')")
        expect(page.locator('.ghost-legend')).to_have_count(0)
        page.keyboard.press('Escape')
        page.wait_for_selector(f'#hub-player-{player}')
        page.locator(f'#hub-player-{player}').click()
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'short')
        ghost.focus()
        page.keyboard.press('Space')
        expect(ghost).to_be_checked()
        expect(ghost).to_be_focused()
        expect(page.locator('.ghost-legend')).to_be_visible()
        page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('ghost') === '1'")
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled')
        smoke.check('player=' in page.url, 'Space skips the shortened entrance and toggles the focused ghost checkbox')
        page.keyboard.press('Space')
        expect(ghost).not_to_be_checked()
        page.wait_for_function("!new URLSearchParams(location.hash.split('?')[1]).has('ghost')")
        expect(page.locator('.ghost-legend')).to_have_count(0)
        smoke.check(True, 'Space toggles ghost comparison off and removes its URL state and legend')
        counts = page.locator('.hub-sample-inline .hub-count')
        t_rounds = counts.last.get_attribute('data-value')
        before_heat = page.locator('.hub-layer-in image').first.get_attribute('href')
        page.get_by_role('button', name='CT', exact=True).click()
        expect(page.get_by_role('button', name='CT', exact=True)).to_have_attribute('aria-pressed', 'true')
        expect(counts.last).to_have_attribute('data-rolling', 'true')
        smoke.check(counts.last.get_attribute('data-value') != t_rounds,
                    'side change reveals the complete new number after the intro has settled')
        page.wait_for_function("!document.querySelector('.hub-count[data-rolling=\"true\"]')")
        smoke.check(page.locator('.hub-layer-in image').first.get_attribute('href') != before_heat,
                    'CT changes the heat texture and side hue independently of team palette')
        # Full entrances must also preserve keyboard activation and input identity.
        page.evaluate('(id) => sessionStorage.removeItem(`hub-intro:${id}`)', player)
        page.reload()
        page.wait_for_selector('.hub-player-view[data-entrance="full"]')
        ghost.focus()
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'full')
        page.keyboard.press('Space')
        expect(ghost).to_be_checked()
        expect(ghost).to_be_focused()
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled')
        page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('ghost') === '1'")
        smoke.check(True, 'Space during the full entrance toggles the focused checkbox and skips the intro')
        ghost.uncheck()
        page.wait_for_function("!new URLSearchParams(location.hash.split('?')[1]).has('ghost')")
        # Force one physical click without waiting out the entrance transform.
        page.evaluate('(id) => sessionStorage.removeItem(`hub-intro:${id}`)', player)
        page.reload()
        page.wait_for_selector('.hub-player-view[data-entrance="full"]')
        expect(ghost).not_to_be_checked()
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'full')
        ghost.click(force=True)
        expect(ghost).to_be_checked()
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled')
        page.wait_for_function("new URLSearchParams(location.hash.split('?')[1]).get('ghost') === '1'")
        smoke.check(True, 'clicking the ghost checkbox during the full entrance toggles it and skips the intro')
        # Reload must restore ghost from the URL, including under reduced motion.
        # Start another full entrance, then change the accessibility preference mid-flight.
        page.evaluate('(id) => sessionStorage.removeItem(`hub-intro:${id}`)', player)
        page.reload()
        page.wait_for_selector('.hub-player-view[data-entrance="full"]')
        page.emulate_media(reduced_motion='reduce')
        expect(page.locator('.hub-player-view')).to_have_attribute('data-entrance', 'settled')
        expect(ghost).to_be_checked()
        ghost.uncheck()
        expect(ghost).not_to_be_checked()
        page.wait_for_function("!new URLSearchParams(location.hash.split('?')[1]).has('ghost')")
        page.wait_for_function("!document.querySelector('.hub-stage').getAnimations({subtree: true}).some(a => a.playState === 'running')")
        smoke.check(page.locator('.hub-intro-skip, .hub-portrait-transfer').count() == 0,
                    'live reduced motion finishes the title sequence and removes transfer layers')
    finally:
        page.unroute_all(behavior='ignoreErrors')
        page.emulate_media(reduced_motion='no-preference')



@route('#/teams-hub?team=vitality', '.hub-team-panel')
def check_match_dates(smoke: Smoke, page: Page) -> None:
    """Deterministic dates exercise the real controls with sample or full exports."""
    root = Path(__file__).resolve().parents[1] / 'public/data'
    index = json.loads((root / 'index.json').read_text())
    index['data_through'] = '2026-08-01'
    teams = json.loads((root / 'heatmap_teams.json').read_text())
    team = next(team for team in teams if team['slug'] == 'vitality')
    profile = json.loads((root / 'de_mirage/teams/vitality.json').read_text())
    # synthetic matches have no timeline file, so the archive must not try to load one
    base = dict(profile['matches'][0], opponent='Date Test Opponent', event='Date Test Event', winprob_available=False)
    rows = [dict(base, demo_id=f'date-test-{i}', hltv_match_id=9000 + i,
                 date=value, date_precision=precision) for i, (value, precision) in enumerate([
                     ('2026-05-12', 'day'), ('2026-06-01', 'event'),
                     ('2026-07-20', 'exact'), (None, None)])]
    profile['matches'] = rows
    map_entry = next(item for item in team['maps'] if item['map'] == 'de_mirage')
    map_entry['results'] = rows
    team['maps'] = [map_entry]
    # The palette searches data/search_index.json (playbook/site_index.py), not the hub file.
    path = root / 'search_index.json'
    search = json.loads(path.read_text()) if path.exists() else {
        'schema_version': 1, 'events': [], 'maps': {'columns': ['map', 'display_name'], 'rows': [['de_mirage', 'Mirage']]},
        'teams': {'columns': ['slug', 'team', 'maps'], 'rows': [['vitality', 'Vitality', [0]]]},
        **{name: {'columns': columns, 'rows': []} for name, columns in [
            ('matches', ['team', 'map', 'demo_id', 'opponent', 'date', 'date_precision', 'event', 'hltv_match_id']),
            ('recipes', ['id', 'map', 'site', 'spots']),
            ('lineups', ['id', 'map', 'side', 'type', 'throw_place', 'land_place', 'n_throws', 'name']),
            ('players', ['steamid', 'name', 'teams'])]}}
    team_i = next(i for i, row in enumerate(search['teams']['rows']) if row[0] == 'vitality')
    map_i = next(i for i, row in enumerate(search['maps']['rows']) if row[0] == 'de_mirage')
    search['events'].append('Date Test Event')
    search['matches']['rows'] = [[team_i, map_i, row['demo_id'], row['opponent'], row['date'], row['date_precision'],
                                  len(search['events']) - 1, row['hltv_match_id']] for row in rows]
    patterns = {
        '**/data/index.json': index,
        '**/data/heatmap_teams.json': teams,
        '**/data/de_mirage/teams/vitality.json': profile,
        '**/data/search_index.json': search,
    }
    try:
        for pattern, payload in patterns.items():
            mock_json(page, pattern, payload)
        page.reload()
        page.locator('.hub-team-results > summary').click()
        results = page.locator('.hub-results')
        expect(results.locator('li')).to_have_count(4)
        smoke.check(results.locator('li').evaluate_all('(rows) => rows.map(row => row.dataset.date)') ==
                    ['2026-07-20', '2026-06-01', '2026-05-12', ''],
                    'archive sorts by date with unknown dates last')
        expect(results.locator('[data-precision=event]')).to_have_text('2026-06 · Date Test Event')
        smoke.check('估算' in results.locator('[data-precision=day]').get_attribute('title'),
                    'estimated day explains its precision in the tooltip')
        results.get_by_role('button', name='近 3 个月', exact=True).click()
        expect(results.locator('li')).to_have_count(3)
        results.get_by_role('button', name='近 1 个月', exact=True).click()
        expect(results.locator('li')).to_have_count(1)
        results.get_by_role('button', name='全部', exact=True).click()
        expect(results.locator('li')).to_have_count(4)
        expect(page.locator('.footer-data-through')).to_contain_text('2026-08-01')
        smoke.check(True, 'calendar windows use data_through and All restores undated matches')
        page.keyboard.press('Control+k')
        page.locator('#palette-query').fill('Date Test Opponent Date Test Event 2026-07-20')
        option = page.locator('.palette-results [role=option]').filter(has_text='2026-07-20').first
        expect(option).to_be_visible()
        option.click()
        archive = page.locator('.hub-team-matches')
        expect(archive).to_have_attribute('open', '')
        expect(archive.locator('.match')).to_have_count(4)
        smoke.check('match=date-test-2' in page.url, 'match search by opponent, event and date opens its archive')
        archive.get_by_role('button', name='近 1 个月', exact=True).click()
        expect(archive.locator('.match')).to_have_count(1)
        smoke.check(True, 'team map archive has the same date window control')
    finally:
        page.unroute_all(behavior='ignoreErrors')


@route('#/de_mirage/tactics', '.tactics-page')
def check_command_palette(smoke: Smoke, page: Page) -> None:
    page.wait_for_load_state('networkidle')
    fetched = []
    page.on('request', lambda request: fetched.append(request.url) if '/data/' in request.url else None)
    page.locator('.palette-trigger').focus()
    page.keyboard.press('Control+k')
    query = page.locator('#palette-query')
    expect(query).to_be_focused()
    # One small search index replaces every map's tactics, lineups and players (F5).
    query.fill('vitality mirage')
    expect(page.locator('.palette-results [role=option]').first).to_be_visible()
    page.wait_for_load_state('networkidle')
    heavy = [url for url in fetched if url.rsplit('/', 1)[-1] in ('lineups.json', 'players.json', 'tactics.json', 'heatmap_teams.json')]
    smoke.check(any(url.endswith('/data/search_index.json') for url in fetched) and not heavy,
                f'palette searches data/search_index.json without per-map files ({heavy[:3]})')
    query.fill('mirage')
    expect(page.locator('.palette-results [role=option]').first).to_be_visible()
    expect(page.locator('.palette-results [role=option]').nth(1)).to_be_visible()
    page.keyboard.press('ArrowDown')
    smoke.check(query.get_attribute('aria-activedescendant') == 'palette-result-1', 'palette supports keyboard result selection')
    page.keyboard.press('Escape')
    expect(page.locator('dialog.command-palette[open]')).to_have_count(0)
    expect(page.locator('.palette-trigger')).to_be_focused()
    page.keyboard.press('Control+k')
    query.fill('Vitality')
    expect(page.locator('.palette-results [role=option]').first).to_contain_text('Vitality')
    page.keyboard.press('Enter')
    page.wait_for_selector('.hub-team-panel')
    smoke.check('team=vitality' in page.url, 'palette Enter opens the matched team')


@route('#/de_mirage/teams/vitality', '.hub-player-card')
def check_team(smoke: Smoke, page: Page) -> None:
    smoke.check('未提供' not in page.inner_text('body'), 'team match metadata omits missing fields')
    smoke.check('#/teams-hub?' in page.url and 'team=vitality' in page.url and 'map=de_mirage' in page.url,
                'legacy team URL redirects to the matching hub slide')
    smoke.check(page.locator('.team-page').count() == 0, 'legacy team page is removed')
    # Redirect must replace the old entry: Back returns to the previous real page.
    page.goto(f"{smoke.base}/#/de_mirage/players")
    page.wait_for_selector('.player-card')
    page.evaluate("location.hash = '/de_mirage/teams/vitality'")
    page.wait_for_selector('.hub-player-card')
    page.go_back()
    page.wait_for_selector('.player-card')
    smoke.check(page.url.endswith('#/de_mirage/players'), 'Back skips the replaced legacy route')
    page.go_forward()
    page.wait_for_selector('.hub-player-card')
    # Team map: the shared low-sample banner follows the exported flag.
    profile = page.request.get(f'{smoke.base}/data/de_mirage/teams/vitality.json').json()
    if profile['low_sample']:
        expect(page.locator('.low-sample')).to_contain_text('样本不足，结果仅供参考。')
    else:
        expect(page.locator('.hub-map-context .low-sample')).to_have_count(0)
    smoke.check(str(profile['n_matches']) in page.locator('.hub-team-matches > summary').inner_text(),
                "team map keeps its match count beside the shared low-sample warning")


@route('#/de_mirage/teams', '.hub-team-card')
def check_teams(smoke: Smoke, page: Page) -> None:
    # The superseded per-map team list redirects to the hub, replacing its history entry.
    smoke.check(page.url.split('#')[-1] == '/teams-hub', 'legacy per-map team list opens the teams hub')
    teams = page.request.get(f'{smoke.base}/data/heatmap_teams.json').json()
    expect(page.locator('.hub-team-card')).to_have_count(len(teams))


@route('#/teams-hub', '.hub-team-card')
def check_team_shields(smoke: Smoke, page: Page) -> None:
    pattern = '**/data/asset_slots.json'
    try:
        mock_json(page, pattern, {'teams': [], 'players': []})
        page.reload()
        page.wait_for_selector('.hub-team-card .team-shield')
        badges = page.locator('.hub-team-card .hub-badge')
        smoke.check(badges.count() == page.locator('.hub-team-card .team-shield').count(),
                    'teams without logos all use the shared neutral shield')
        smoke.check(all(len(text.strip()) > 1 for text in page.locator('.team-shield text').all_text_contents()),
                    'shield placeholders show short team names rather than single letters')
    finally:
        page.unroute_all(behavior='ignoreErrors')


@route('#/teams-hub?team=vitality&map=de_mirage&player=76561198113666193&side=T', '.hub-player-view')
def check_radar6(smoke: Smoke, page: Page) -> None:
    root = Path(__file__).resolve().parents[1]
    players = json.loads((root / 'public/data/de_mirage/players.json').read_text())
    axes = ['entry', 'trade', 'lurk_distance', 'space_gain', 'utility_impact', 'clutch_wpa']
    for player in players:
        for side in ['T', 'CT']:
            player[side]['radar_6d'] = {
                'rounds': 60, 'eligible': True,
                **{axis: {'raw': .2, 'percentile': 75 if side == 'T' else 25,
                          'reference_players': 10} for axis in axes},
            }
        player['CT']['radar_6d']['lurk_distance'] = {'raw': None, 'percentile': None, 'reference_players': 0}
    pattern = '**/data/de_mirage/players.json'
    try:
        mock_json(page, pattern, players)
        page.reload()
        page.emulate_media(reduced_motion='reduce')
        for width, height in [(1440, 900), (1280, 800)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('window.scrollTo(0, 0)')
            page.wait_for_timeout(100)
            controls = page.locator('.hub-map-main .hub-map-controls').bounding_box()
            radar = page.locator('.hub-map-main .hub-radar').bounding_box()
            smoke.check(controls is not None and radar is not None and controls['y'] >= 0 and
                        controls['y'] + controls['height'] <= radar['y'] + 1 and
                        radar['width'] > 200 and radar['y'] + radar['height'] <= height,
                        f'{width}x{height}: layer/phase controls and complete player radar fit without scrolling')
            check_segmented_layout(smoke, page)
        page.set_viewport_size({'width': 1440, 'height': 900})
        chart = page.locator('.hub-player-analysis > .player-radar6')
        expect(chart).to_have_attribute('data-side', 'T')
        smoke.check(chart.locator('[data-axis]').count() == 6, 'player radar has six focusable axes')
        smoke.check(chart.locator('[data-axis][tabindex="0"]').count() == 1, 'the six axes share one Tab stop (roving tabindex)')
        chart.locator('[data-axis=entry]').focus()
        expect(chart.locator('[role=status]')).to_contain_text('P75.0')
        page.keyboard.press('ArrowRight')
        expect(chart.locator('[data-axis=trade]')).to_be_focused()
        expect(chart.locator('[data-axis=trade]')).to_have_attribute('tabindex', '0')
        page.keyboard.press('ArrowLeft')
        expect(chart.locator('[data-axis=entry]')).to_be_focused()
        page.get_by_role('button', name='CT', exact=True).click()
        expect(chart).to_have_attribute('data-side', 'CT')
        chart.locator('[data-axis=entry]').focus()
        expect(chart.locator('[role=status]')).to_contain_text('P25.0')
        expect(chart.locator('[data-axis=lurk_distance]')).to_contain_text('—')
        smoke.check(True, 'side switch updates percentiles and CT lurk is unavailable')
    finally:
        page.unroute_all(behavior='ignoreErrors')


@route('#/de_mirage/players', 'text=ZywOo')
def check_players(smoke: Smoke, page: Page) -> None:
    pbody = page.inner_text("body")
    smoke.check("狙击手" in pbody or "AWPer" in pbody, "players page shows role hints (ZywOo AWPer)")

    # Language switch persists across reload
    zh_title = page.inner_text("h1")
    try:
        page.locator("header button", has_text="EN").first.click() if page.locator("header button", has_text="EN").count() else page.locator(".lang-toggle, header button").last.click()
        page.reload()
        page.wait_for_selector("text=ZywOo")
        smoke.check(page.inner_text("h1") != zh_title and page.evaluate("document.documentElement.lang") == "en",
              "language switches to English and persists after reload")
    finally:
        # localStorage is shared by every page of the context: later routes expect Chinese.
        page.evaluate("localStorage.setItem('cs2-pro-playbook.lang', 'zh')")


# Chromium can retain layout boxes below a closed <details>. Client rects alone
# therefore do not establish that a track (or its unmeasured highlight) is shown.
SEGMENTED_LAYOUT = r"""() => {
    const mismatches = [], skipped = [], labelMismatches = [];
    const rect = element => {
        if (!element) return null;
        const bounds = element.getBoundingClientRect();
        return Object.fromEntries(['x', 'y', 'width', 'height'].map(key => [key, bounds[key]]));
    };
    for (const [index, track] of [...document.querySelectorAll('.hud-segmented')].entries()) {
        const selected = track.querySelector('button[aria-pressed="true"], button[aria-selected="true"]');
        const detail = {index, class: track.className, pressed: selected?.textContent.trim() ?? null};
        let closed = null;
        for (let ancestor = track.parentElement; ancestor; ancestor = ancestor.parentElement) {
            if (ancestor.tagName !== 'DETAILS' || ancestor.open) continue;
            const summary = [...ancestor.children].find(child => child.tagName === 'SUMMARY');
            if (!summary?.contains(track)) { closed = ancestor; break; }
        }
        const highlight = track.querySelector('.segment-highlight');
        const button = rect(selected), light = rect(highlight);
        const deltas = button && light ? Object.fromEntries(
            ['x', 'y', 'width', 'height'].map(key => [key, light[key] - button[key]])
        ) : null;
        const bounds = rect(track);
        const reason = closed ? `closed details: ${closed.className}` :
            !track.checkVisibility({visibilityProperty: true}) ? 'not rendered/visibility hidden' :
            bounds.width <= 0 || bounds.height <= 0 ? 'zero-size track' : null;
        if (reason) {
            skipped.push({...detail, reason, button, highlight: light, deltas});
            continue;
        }
        for (const button of track.querySelectorAll(':scope > button')) {
            if (!button.checkVisibility({visibilityProperty: true})) continue;
            const style = getComputedStyle(button);
            const range = document.createRange(); range.selectNodeContents(button);
            const lines = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
            if (style.whiteSpace !== 'nowrap' || style.flexShrink !== '0' ||
                !lines.every(r => Math.abs(r.top - lines[0].top) < 1) ||
                button.scrollWidth > button.clientWidth + 1) {
                labelMismatches.push({...detail, label: button.textContent.trim()});
            }
        }
        if (!selected) continue;
        const animating = highlight?.getAnimations().some(animation =>
            animation.playState === 'running' || animation.pending) ?? false;
        if (!light || button.width <= 0 || button.height <= 0 || animating ||
            Object.values(deltas).some(delta => Math.abs(delta) > 1.5)) {
            mismatches.push({...detail, button, highlight: light, deltas, animating});
        }
    }
    return {mismatches, skipped, labelMismatches};
}"""


def check_segmented_layout(smoke: Smoke, page: Page) -> None:
    for width, height in [(1440, 900), (1280, 800)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.evaluate('document.fonts.ready.then(() => undefined)')
        # Return the final mismatches before Playwright's outer timeout, instead
        # of losing the offending track/state in a generic wait_for_function error.
        # Poll through transitions; never exempt transformed/animating tracks.
        report_handle = page.wait_for_function(f"""deadline => {{
            const report = ({SEGMENTED_LAYOUT})();
            return !report.mismatches.length || Date.now() >= deadline ? report : false;
        }}""", arg=page.evaluate('Date.now()') + 9_000, timeout=10_000)
        try:
            report = report_handle.json_value()
        finally:
            report_handle.dispose()
        diagnostics = json.dumps(report, ensure_ascii=False)
        # Keep evidence for false positives too: identify the hidden tracks that
        # the former client-rect-only check would have rejected.
        excluded = [{key: track[key] for key in ('class', 'pressed', 'reason', 'deltas')}
                    for track in report['skipped'] if track['deltas'] and
                    any(abs(delta) > 1.5 for delta in track['deltas'].values())]
        if excluded:
            print(f'info {width}x{height}: excluded non-rendered segmented mismatches on {page.url}: '
                  + json.dumps(excluded, ensure_ascii=False))
        smoke.check(not report['mismatches'],
                    f'{width}x{height}: segmented highlight matches the pressed button after fonts/resize'
                    + (f' on {page.url}: {diagnostics}' if report['mismatches'] else ''))
        smoke.check(not report['labelMismatches'],
                    f'{width}x{height}: segmented labels stay on one line at {page.url.split("#")[-1]}'
                    + (f': {diagnostics}' if report['labelMismatches'] else ''))
    page.set_viewport_size({'width': 1440, 'height': 900})


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
            check_segmented_layout(smoke, page)
            case.test(smoke, page)
            check_segmented_layout(smoke, page)
    except Exception as error:
        # Preserve the failing page and continue so one route cannot hide others.
        smoke.check(False, f"{label} ({case.path}): {error}")
    finally:
        # A failed assertion must not disable motion in every subsequent route.
        page.emulate_media(reduced_motion='no-preference')
        if smoke.shots:
            try:
                page.screenshot(path=str(smoke.shots / f"{label}.png"), full_page=True)
            except Exception as error:
                smoke.check(False, f"could not capture {label}: {error}")


def run_routes(smoke: Smoke, context: BrowserContext, *, mobile: bool = False,
               cases: list[Route] | None = None) -> None:
    for case in ROUTES if cases is None else cases:
        # Removing network routes does not clear data.ts's in-memory fetch cache
        # or close dialogs. A fresh document makes failures independent.
        page = context.new_page()
        try:
            page.set_default_timeout(10_000)
            smoke.watch(page)
            run_route(smoke, case, page, mobile=mobile)
        finally:
            page.close()


@route('#/lab', '.ai-lab-page')
def check_ai_lab(smoke: Smoke, page: Page) -> None:
    data = page.request.get(f'{smoke.base}/data/ai_lab.json').json()
    panels = page.locator('[data-lab-panel]')
    expect(panels).to_have_count(4)
    smoke.check(set(panels.evaluate_all("els => els.map(el => el.dataset.labPanel)")) ==
                {'attention', 'shap', 'control', 'references'}, 'AI lab has its four research panels')
    expect(page.locator('.lab-reference')).to_have_count(len(data['references']))
    smoke.check(page.locator('.lab-reference').evaluate_all("els => els.map(el => el.dataset.referenceId)") ==
                [r['id'] for r in data['references']], 'AI lab references exactly match the verified export')
    expect(page.locator('.lab-paper-note')).to_contain_text('论文结论（Dust2）')
    smoke.check(data['metadata']['paper_scope'].split('(')[1].split(' rounds')[0] in page.locator('.lab-paper-note').inner_text(), 'paper sample count comes from the export')
    expect(page.locator('.lab-paper-note')).to_contain_text('下方结果均由本项目的比赛录像计算得出')
    expect(page.locator('.lab-limitations')).to_contain_text('回放中的 T 控图率是独立观测指标')
    expect(page.locator('.lab-method').last).to_contain_text('轻量标准化、主成分分析与 K 均值聚类')
    expect(page.locator('.lab-references a')).to_have_text([r['title'] for r in data['references']])
    smoke.check(True, 'paper claims are confined to a distinct Dust2 note')
    expect(page.locator('.main-nav a[href="#/lab"]')).to_have_count(1)
    for slider in ('SHAP 时间轴', '阵型快照'):
        page.get_by_role('slider', name=slider, exact=True).focus()
        page.keyboard.press('End')
    residual = float(page.locator('.shap-additivity').get_attribute('data-residual'))
    smoke.check(abs(residual) < 1e-6, 'SHAP grouped contributions remain additive after scrubbing')
    active_groups = data['shap'].get('active_groups', [g for g in data['shap']['groups']
        if any(state['shap_values'].get(g, 0) != 0 for r in data['shap']['rounds'] for state in r['states'])])
    smoke.check(page.locator('.shap-row').evaluate_all("els => els.map(el => el.dataset.group)") == active_groups,
                'SHAP renders only exported active groups, or nonzero groups for legacy data')
    if data['shap'].get('inactive_groups_note_zh'):
        expect(page.locator('.shap-inactive-note')).to_have_text(data['shap']['inactive_groups_note_zh'])
    accuracy = data.get('model_accuracy')
    if accuracy:
        expected = f"{accuracy['folds']} 折按比赛留出验证 · {accuracy['matches']} 场比赛 · {accuracy['rows']:,} 个秒级状态"
        expect(page.locator('[data-lab-panel=references]')).to_contain_text(expected)
        smoke.check(True, 'all validation sample counts match model_accuracy JSON')
    patterns = page.request.get(f'{smoke.base}/data/de_mirage/ct_patterns.json').json()
    replay_index = page.request.get(f'{smoke.base}/data/de_mirage/replay/index.json').json()
    points = patterns['embedding']['points']
    expect(page.locator('.lab-cloud circle')).to_have_count(len(points))
    unavailable = [i for i, point in enumerate(points) if not point.get('replay_available',
                   point['round_num'] in replay_index.get(point['demo_id'], []))]
    expect(page.locator('.lab-cloud circle[aria-disabled=true]')).to_have_count(len(unavailable))
    if unavailable:
        dot = page.locator('.lab-cloud circle').nth(unavailable[0])
        expect(dot.locator('title')).to_contain_text('无回放')
        smoke.check(float(dot.get_attribute('opacity')) < .2, 'unavailable scatter points are dimmed')
        selected = page.get_by_label('键盘选择样本')
        before = selected.input_value()
        dot.dispatch_event('click')
        smoke.check(selected.input_value() == before, 'unavailable scatter clicks cannot change the selected round')
        # Playwright's to_be_disabled() reports <option disabled> as enabled; read the DOM property.
        smoke.check(selected.locator('option').nth(unavailable[0] + 1).evaluate('el => el.disabled'),
                    'unavailable rounds are disabled in the keyboard sample picker')
    available = next((i for i in range(len(points)) if i not in set(unavailable)), None)
    if available is not None:
        page.locator('.lab-cloud circle').nth(available).focus()
        page.keyboard.press('Enter')
        point = points[available]
        expect(page.get_by_label('键盘选择样本')).to_have_value(f"{point['demo_id']}:{point['round_num']}:{point['team']}")
    smoke.check('未导出此回合回放' not in page.inner_text('body'), 'medoids never lead to the missing-replay dead end')
    # The lab route has no map segment: its replay must request the attention map's file (F2).
    opener = page.locator('[data-lab-panel=attention] .replay-open').first
    if opener.count():
        with page.expect_request(lambda request: '/replay/' in request.url and request.url.endswith('.json')
                                 and '/replay/index.json' not in request.url) as replay_request:
            opener.click()
        smoke.check('/data/de_' in replay_request.value.url and '/data/lab/' not in replay_request.value.url,
                    f'lab replay requests the map replay file ({replay_request.value.url.split("/data/")[-1]})')
        expect(page.locator('dialog[open] .replay-radar')).to_have_count(1)
        smoke.check('map=de_' in page.url, 'lab replay URL names its map')
        page.keyboard.press('Escape')
        expect(page.locator('dialog[open]')).to_have_count(0)
        smoke.check(page.url.split('#')[-1].startswith('/lab') and 'replay=' not in page.url, 'closing the lab replay restores the lab URL')
    control = data['control']
    if control:
        expect(page.locator('.lab-control-radar [data-cell]')).to_have_count(
            sum(cell['occupied'] for cell in control['cells']))
        page.get_by_role('button', name='💨 烟雾反事实', exact=True).click()
        expect(page.locator('.lab-control-radar')).to_have_attribute('data-mode', 'before')
        page.get_by_role('button', name='显示投烟后', exact=True).click()
        expect(page.locator('.lab-control-radar')).to_have_attribute('data-mode', 'after')
        actual = page.locator('.lab-control-radar [data-cell]').evaluate_all(
            "els => els.map(el => [Number(el.dataset.cell), el.querySelector('title').textContent.split(' · ')[0]])")
        smoke.check(all(owner == control['smoke_simulation']['ownership_after'][i] for i, owner in actual),
                    'smoke counterfactual paints the exported cell ownership without invented gains')


@route('#/de_mirage/tactics?side=CT', '.ct-cluster-card')
def check_ct_defense(smoke: Smoke, page: Page) -> None:
    data = page.request.get(f'{smoke.base}/data/de_mirage/ct_patterns.json').json()
    lab = page.request.get(f'{smoke.base}/data/ai_lab.json').json()
    cards = page.locator('.ct-cluster-card')
    expect(cards).to_have_count(len(data['clusters']))
    shares = cards.evaluate_all("els => els.map(el => Number(el.dataset.share))")
    smoke.check(abs(sum(shares) - 1) < 1e-6, 'CT cluster cards match the export and shares sum to one')
    for c in data['clusters']:
        card = page.locator(f'.ct-cluster-card[data-cluster-id="{c["id"]}"]')
        expect(card).to_contain_text(c['label_zh'])
        expect(card).to_contain_text('95% CI')
    chosen = data['clusters'][-1]
    page.locator(f'.ct-cluster-card[data-cluster-id="{chosen["id"]}"]').click()
    expect(page.locator('.ct-cluster-card[aria-pressed="true"]')).to_have_attribute('data-cluster-id', chosen['id'])
    radar = page.locator('.ct-defense .tactics-radar-wrap')
    expect(radar).to_have_attribute('data-recipe-id', chosen['id'])
    expect(radar.locator('path[data-kind="mean"]')).to_have_count(0)
    if any(a['map'] == data['map'] and a['cluster_id'] == chosen['id'] for a in lab['attention']):
        expect(radar.locator('path[data-kind="medoid"]')).to_have_count(5)
        expect(radar.locator('.ct-medoid circle')).to_have_count(10)
        expect(radar.locator('.ct-medoid circle[data-time="10"]')).to_have_count(5)
        expect(radar.locator('.ct-medoid circle[data-time="20"]')).to_have_count(5)
    smoke.check(radar.locator('.ct-trajectory-path').evaluate_all(
        "els => els.length > 0 && els.every(el => el.getAttribute('d').includes('L'))"),
        'CT card selection draws real multi-snapshot trajectory paths on the existing radar')
    expect(radar.locator('path[data-kind="sample"]')).to_have_count(0)
    toggle = page.get_by_role('checkbox', name='叠加簇均值轨迹', exact=True)
    expect(toggle).not_to_be_checked()
    toggle.check()
    expect(radar.locator('path[data-kind="mean"]')).to_have_count(5)
    expect(radar.locator('path[data-kind="sample"]')).to_have_count(0)
    toggle.uncheck()
    expect(radar.locator('path[data-kind="mean"]')).to_have_count(0)
    smoke.check(True, 'default CT radar has medoid endpoints only; mean overlay is opt-in and samples are absent')
    chi = data['chi_square']
    expect(page.locator('.ct-chi')).to_contain_text(f"χ² = {chi['statistic']:.2f} · df = {chi['dof']}")
    if chi.get('p_display'):
        expect(page.locator('.ct-chi')).to_contain_text(chi['p_display'])
    elif chi['p'] < 1e-4:
        expect(page.locator('.ct-chi')).to_contain_text('p < 0.0001')
    if chi.get('cramers_v') is not None:
        expect(page.locator('.ct-chi')).to_contain_text(f"Cramér's V = {chi['cramers_v']:.2f}")
    excluded = data['metadata'].get('excluded_pistol_rounds')
    if excluded is not None:
        expect(page.locator('.ct-pistol-note')).to_have_text(f'已排除手枪局 {excluded:,} 回合')
    if data['chi_square']['caveat'] or (data['chi_square']['min_expected'] or 5) < 5:
        expect(page.locator('.ct-chi .lab-warning')).to_be_visible()


@route('#/lab', '.ai-lab-page')
def check_lab_legacy_v41(smoke: Smoke, page: Page) -> None:
    """Exercise compatibility even when the real export already has new fields."""
    lab = page.request.get(f'{smoke.base}/data/ai_lab.json').json()
    patterns = page.request.get(f'{smoke.base}/data/de_mirage/ct_patterns.json').json()
    lab['shap'].pop('active_groups', None)
    lab['shap'].pop('inactive_groups_note_zh', None)
    for sample in lab['shap']['rounds']:
        for state in sample['states']:
            state['shap_values']['active_utility'] = 0
            state['shap_values']['positional_spread_pinch'] = 0
    # A later nonzero example keeps the group visible in the first state too.
    lab['shap']['rounds'][-1]['states'][-1]['shap_values']['active_utility'] = .1
    lab['model_accuracy'].update(folds=7, matches=321, rows=123456)
    patterns['embedding']['points'][0]['replay_available'] = False
    patterns['chi_square'].pop('p_display', None)
    patterns['chi_square'].pop('cramers_v', None)
    patterns['chi_square']['p'] = 1e-107
    patterns['metadata'].pop('excluded_pistol_rounds', None)
    lab_pattern, ct_pattern = '**/data/ai_lab.json', '**/data/de_mirage/ct_patterns.json'
    try:
        mock_json(page, lab_pattern, lab)
        mock_json(page, ct_pattern, patterns)
        page.reload()
        expect(page.locator('.shap-row[data-group=active_utility]')).to_have_count(1)
        expect(page.locator('.shap-row[data-group=positional_spread_pinch]')).to_have_count(0)
        expect(page.locator('[data-lab-panel=references]')).to_contain_text(
            '7 折按比赛留出验证 · 321 场比赛 · 123,456 个秒级状态')
        dot = page.locator('.lab-cloud circle').first
        expect(dot).to_have_attribute('aria-disabled', 'true')
        dot.dispatch_event('click')
        expect(page.get_by_label('键盘选择样本')).to_have_value('')
        page.goto(f'{smoke.base}/#/de_mirage/tactics?side=CT')
        expect(page.locator('.ct-chi')).to_contain_text('p < 0.0001')
        observed = patterns['chi_square'].get('observed', [])
        n = sum(sum(row) for row in observed)
        dimension = min(len(observed) - 1, len(observed[0]) - 1) if observed else 0
        if n > 0 and dimension > 0:
            effect = (patterns['chi_square']['statistic'] / (n * dimension)) ** .5
            expect(page.locator('.ct-chi')).to_contain_text(f"Cramér's V = {effect:.2f}")
        expect(page.locator('.ct-pistol-note')).to_have_count(0)
        smoke.check(True, 'legacy fields fall back across all SHAP examples, replay gating, dynamic validation and CT statistics')
    finally:
        page.unroute(lab_pattern)
        page.unroute(ct_pattern)


@route('#/teams-hub?team=falcons&map=de_mirage', '.team-fingerprint')
def check_team_fingerprint(smoke: Smoke, page: Page) -> None:
    data = page.request.get(f'{smoke.base}/data/de_mirage/ct_patterns.json').json()
    fingerprint = next(f for f in data['fingerprints'] if f['team'].lower() == 'falcons')
    panel = page.locator('.team-fingerprint')
    expect(panel).to_have_attribute('data-n', str(fingerprint['n']))
    expect(panel.locator('.fingerprint-row')).to_have_count(len(fingerprint['usage']))
    for row in fingerprint['usage']:
        item = panel.locator(f'.fingerprint-row[data-cluster-id="{row["cluster_id"]}"]')
        actual = item.evaluate("el => [Number(el.dataset.share), Number(el.dataset.proShare)]")
        smoke.check(abs(actual[0] - row['share']) < 1e-9 and abs(actual[1] - row['pro_share']) < 1e-9,
                    f'fingerprint {row["cluster_id"]}: team and league bars use exported shares')
    profile = page.request.get(f'{smoke.base}/data/de_mirage/teams/falcons.json').json()
    recipes = len({r['value'] for r in profile.get('tactics', {}).get('T', {}).get('recipes', [])})
    summary = page.locator('.hub-team-basis > summary')
    smoke.check('数据依据（0 条）' not in summary.inner_text(), 'team map never presents zero evidence as a basis')
    if recipes:
        expect(summary).to_contain_text(f'收录 {recipes} 套进攻套路')
    if data['clusters']:
        expect(summary).to_contain_text(f"{len(data['clusters'])} 类 CT 阵型")
    profile_pattern = '**/data/de_mirage/teams/falcons.json'
    profile['insights'] = []
    try:
        mock_json(page, profile_pattern, profile)
        page.reload()
        expect(summary).to_contain_text(f"{len(data['clusters'])} 类 CT 阵型")
        smoke.check('数据依据（0 条）' not in summary.inner_text(), 'empty evidence retains real tactical coverage counts')
    finally:
        page.unroute(profile_pattern)
    # Reload clears the app cache; test the inclusive visibility threshold in isolation.
    pattern = '**/data/de_mirage/ct_patterns.json'
    original_n = fingerprint['n']
    try:
        fingerprint['n'] = 30
        mock_json(page, pattern, data)
        page.reload()
        expect(panel).to_have_attribute('data-n', '30')
        page.unroute(pattern)
        fingerprint['n'] = 29
        mock_json(page, pattern, data)
        with page.expect_response(lambda response: '/data/de_mirage/ct_patterns.json' in response.url):
            page.reload()
        page.wait_for_selector('.hub-map-context')
        page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        expect(panel).to_have_count(0)
        smoke.check(True, 'fingerprint is visible at 30 CT rounds and hidden below 30')
    finally:
        page.unroute(pattern)
        fingerprint['n'] = original_n
        page.reload()
        expect(panel).to_have_attribute('data-n', str(original_n))


@route('#/teams-hub?team=vitality', '.hub-orbit-node')
def check_hub_map_loading_v41(smoke: Smoke, page: Page) -> None:
    held = []
    pattern = '**/data/de_mirage/heatmaps/teams/vitality.json'
    page.route(pattern, lambda intercepted: held.append(intercepted))
    page.evaluate("""() => {
        window.hubClickAt = performance.now();
        window.hubShellDelay = null;
        window.hubSnapshotWait = 0;
        window.hubFadeDurations = [];
        window.hubOriginalTransition = document.startViewTransition;
        window.hubOriginalAnimate = Element.prototype.animate;
        if (document.startViewTransition) {
            document.startViewTransition = function(update) {
                // The browser renders and captures the old scene before it runs the update;
                // that capture is slow on GPU-less runners and is not the app's latency.
                const requested = performance.now();
                const transition = window.hubOriginalTransition.call(this, () => {
                    window.hubSnapshotWait += performance.now() - requested;
                    return update();
                });
                transition.ready.then(() => {
                    window.hubFadeDurations = document.getAnimations()
                        .filter(a => ['hub-scene-in', 'hub-scene-out'].includes(a.animationName))
                        .map(a => a.effect.getTiming().duration);
                }).catch(() => {});
                return transition;
            };
        } else {
            Element.prototype.animate = function(frames, options) {
                if (this.classList.contains('hub-stage')) window.hubFadeDurations.push(options.duration);
                return window.hubOriginalAnimate.call(this, frames, options);
            };
        }
        window.hubShellObserver = new MutationObserver(() => {
            if (document.querySelector('.hub-map-skeleton')) {
                window.hubShellDelay = performance.now() - window.hubClickAt;
                window.hubShellObserver.disconnect();
            }
        });
        window.hubShellObserver.observe(document.body, {childList:true, subtree:true});
    }""")
    try:
        page.locator('#hub-map-de_mirage').dispatch_event('click')
        expect(page.locator('.hub-map-panel')).to_be_visible()
        expect(page.locator('.hub-player-skeleton')).to_have_count(5)
        expect(page.locator('.hub-map-panel .loading')).to_have_count(0)
        expect(page.locator('.hub-orbit-core')).to_have_count(0)
        expect(page.locator('.hub-section-head h2')).to_have_count(1)
        delay, snapshot = page.evaluate('[window.hubShellDelay, window.hubSnapshotWait]')
        app_delay = None if delay is None else round(delay - snapshot)
        smoke.check(app_delay is not None and app_delay <= 200,
                    f'slow data: destination shell appears within 200ms ({app_delay}ms app time; '
                    f'{round(snapshot)}ms browser view-transition capture), with portraits and one title')
        smoke.check(page.locator('.hub-section-head [style*=view-transition-name]').count() == 0,
                    'team/map titles do not fly independently of the scene')
        page.wait_for_function('window.hubFadeDurations.length > 0')
        durations = page.evaluate('window.hubFadeDurations')
        smoke.check(all(duration == 180 for duration in durations),
                    f'actual scene fade animations use 180ms opacity timing: {durations}')
        for intercepted in held:
            intercepted.continue_()
        page.unroute(pattern)
        page.wait_for_selector('.hub-player-card')
        page.keyboard.press('Escape')
        expect(page.locator('#hub-map-de_mirage')).to_be_focused()
        page.emulate_media(reduced_motion='reduce')
        page.locator('#hub-map-de_mirage').dispatch_event('click')
        expect(page.locator('.hub-stage')).to_have_css('view-transition-name', 'none')
        smoke.check(True, 'reduced-motion map swap is instant and return focus survives the fade')
    finally:
        page.unroute(pattern)
        page.evaluate('''() => {
            window.hubShellObserver?.disconnect();
            if (window.hubOriginalTransition) document.startViewTransition = window.hubOriginalTransition;
            Element.prototype.animate = window.hubOriginalAnimate;
        }''')


@route('#/de_mirage/tactics?side=CT', '.tactics-radar-wrap')
def check_tactics_radar_size(smoke: Smoke, page: Page) -> None:
    """A radar whose workspace starts below the fold must not collapse (F1); lineups stay lazy (F6)."""
    page.wait_for_load_state('networkidle')
    for width, height in [(1440, 900), (1280, 800)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        widths = page.locator('svg.tactics-radar').evaluate_all('els => els.map(el => Math.round(el.getBoundingClientRect().width))')
        smoke.check(bool(widths) and min(widths) >= 280, f'{width}x{height}: every tactics radar is at least 280px wide {widths}')
    page.set_viewport_size({'width': 1440, 'height': 900})
    fetched = []
    page.on('request', lambda request: fetched.append(request.url) if '/data/' in request.url else None)
    page.goto(f'{smoke.base}/#/de_mirage/tactics?side=T')
    page.reload()
    page.wait_for_selector('.tactics-page')
    page.wait_for_load_state('networkidle')
    smoke.check(any(url.endswith('/de_mirage/lineup_index.json') for url in fetched)
                and not any(url.endswith('/lineups.json') for url in fetched),
                'tactics reads the small lineup index, not the full lineup library')


@route('#/de_mirage/tactics', '.tactics-page')
def check_replay_keyboard(smoke: Smoke, page: Page) -> None:
    """Space activates the focused dialog control instead of toggling playback (F8)."""
    pattern = '**/data/de_mirage/replay/smoke-keys/1.json'
    try:
        page.route(pattern, lambda request: request.fulfill(json={**replay_fixture(), 'demo_id': 'smoke-keys'}))
        page.emulate_media(reduced_motion='reduce')
        page.goto(f'{smoke.base}/#/de_mirage/tactics?replay=smoke-keys:1')
        page.wait_for_selector('dialog[open] .replay-radar')
        play = page.get_by_role('button', name='播放', exact=True)
        expect(play).to_be_visible()
        speed = page.get_by_role('button', name='2×', exact=True)
        speed.focus()
        page.keyboard.press('Space')
        expect(speed).to_have_attribute('aria-pressed', 'true')
        expect(play).to_be_visible()
        smoke.check(True, 'Space on a focused speed button changes the speed, not playback')
        play.focus()
        page.keyboard.press('Space')
        expect(page.get_by_role('button', name='暂停', exact=True)).to_be_visible()
        page.keyboard.press('Space')
        expect(page.get_by_role('button', name='播放', exact=True)).to_be_visible()
        smoke.check(True, 'Space on the focused play button plays and pauses exactly once per press')
        page.locator('.replay-close').focus()
        page.keyboard.press('Space')
        expect(page.locator('dialog[open]')).to_have_count(0)
        smoke.check('replay=' not in page.url, 'Space activates the focused Close button')
    finally:
        page.unroute_all(behavior='ignoreErrors')
        page.emulate_media(reduced_motion='no-preference')


@route('#/de_mirage/tactics', '.tactics-page')
def check_error_boundaries(smoke: Smoke, page: Page) -> None:
    """Malformed data fails locally with a Chinese message; nav, footer and dialogs survive (F3)."""
    root = Path(__file__).resolve().parents[1] / 'public/data'
    tactics = json.loads((root / 'de_mirage/tactics.json').read_text())
    pattern = '**/data/de_mirage/tactics.json'
    try:
        mock_json(page, pattern, {})
        page.reload()
        expect(page.locator('.route-scene .notice-error')).to_contain_text('数据格式与当前页面不匹配')
        expect(page.locator('.route-scene .notice-error')).to_contain_text('返回地图')
        expect(page.locator('.main-nav')).to_be_visible()
        expect(page.locator('footer a[href="#/about"]')).to_be_visible()
        smoke.check(True, 'a malformed data file shows a localized notice and keeps the shell')
        page.unroute(pattern)
        # Right top-level shape, missing nested field: a render error, caught by the route boundary.
        mock_json(page, pattern, {**tactics, 't_overview': {}})
        logged = len(smoke.errors)
        page.reload()
        expect(page.locator('.route-error')).to_contain_text('此页面暂时无法显示')
        expect(page.locator('.main-nav')).to_be_visible()
        page.locator('.main-nav a[href="#/lab"]').click()
        expect(page.locator('.route-error')).to_have_count(0)
        produced, smoke.errors[logged:] = smoke.errors[logged:], []
        smoke.check(all('ErrorBoundary' in error or 'Error' in error or 'undefined' in error for error in produced),
                    f'only the injected render error was logged ({len(produced)} entries)')
        smoke.check(True, 'a render error is contained by the route boundary and navigation recovers')
        page.unroute(pattern)
        mock_json(page, '**/data/de_mirage/replay/smoke-broken/1.json', {})
        # Reload first: the app caches the broken tactics.json in memory, and a hash
        # navigation back to the tactics page would render (and log) it again.
        page.reload()
        page.goto(f'{smoke.base}/#/de_mirage/tactics?replay=smoke-broken:1')
        expect(page.locator('dialog[open] .replay-error')).to_contain_text('回放数据不完整')
        expect(page.locator('.tactics-page')).to_be_visible()
        page.locator('.replay-close').click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        smoke.check(True, 'a broken replay round stays inside its dialog')
    finally:
        page.unroute_all(behavior='ignoreErrors')


@route('#/about', '.about-page')
def check_about(smoke: Smoke, page: Page) -> None:
    expect(page.locator('main h1')).to_have_text('数据来源与版权')
    text = page.locator('.about-page').inner_text()
    terms = ('GOTV', 'HLTV.org', 'cs2povarchive/cs2-demos', 'Apache-2.0', 'bo3.gg', 'awpy', 'Valve', 'MIT')
    smoke.check(all(term in text for term in terms), 'about page credits sources, licences and trademarks')
    smoke.check(text.index('比赛数据') < text.index('Match data'), 'about page is bilingual, Chinese first')
    page.goto(f'{smoke.base}/#/')
    footer = page.locator('footer')
    smoke.check('Professional CS2 match demos' not in footer.inner_text(), 'footer shows the localized credit line, not raw export text')
    footer.locator('a[href="#/about"]').click()
    expect(page.locator('.about-page')).to_be_visible()


@route('#/teams-hub?team=vitality&map=de_mirage', '.hub-player-card')
def check_match_replays(smoke: Smoke, page: Page) -> None:
    """Rows with replay rounds but no win-probability strip still open them (F11)."""
    root = Path(__file__).resolve().parents[1] / 'public/data'
    team = json.loads((root / 'de_mirage/teams/vitality.json').read_text())
    demo = team['matches'][0]['demo_id']
    for match in team['matches']:
        match['winprob_available'] = False
    try:
        mock_json(page, '**/data/de_mirage/teams/vitality.json', team)
        mock_json(page, '**/data/de_mirage/replay/index.json', {demo: [3, 1]})
        page.route(f'**/data/de_mirage/replay/{demo}/3.json', lambda request: request.fulfill(json={**replay_fixture(), 'demo_id': demo, 'round_num': 3}))
        page.reload()
        page.wait_for_selector('.hub-player-card')
        page.locator('.hub-team-matches > summary').click()
        chips = page.locator('.match .match-replays')
        expect(chips).to_have_count(1)
        expect(chips.locator('summary')).to_contain_text('2')
        chips.locator('summary').click()
        smoke.check(chips.locator('.replay-open').all_text_contents() == ['1', '3'], 'replay chips list the indexed rounds in order')
        chips.get_by_role('button', name='回放第 3 回合', exact=True).click()
        expect(page.locator('dialog[open] .replay-title-match')).to_contain_text('第 3 回合')
        page.keyboard.press('Escape')
        expect(page.locator('dialog[open]')).to_have_count(0)
        smoke.check('map=de_mirage' in page.url and 'team=vitality' in page.url, 'replay chips open and close within the hub slide')
    finally:
        page.unroute_all(behavior='ignoreErrors')


# Real-export checks: the committed samples/site lacks ai_lab.json, ct_patterns.json and
# showcase teams such as Falcons. `--samples` skips them (CI); run them before publishing.
REAL_DATA_ONLY = ('check_ai_lab', 'check_lab_legacy_v41', 'check_ct_defense', 'check_team_fingerprint')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="http://localhost:4173")
    parser.add_argument("--shots", type=Path, help="save each route, including on exceptions")
    parser.add_argument("--lab-only", action="store_true", help="check AI lab, CT defense and fingerprints using the current export")
    parser.add_argument("--orbit-only", action="store_true", help="check orbit navigation/layout with current data")
    parser.add_argument("--samples", action="store_true",
                        help="committed samples/site (CI): skip the checks that need a full export")
    parser.add_argument("--mobile", action="store_true", help="also check 375px pages for horizontal overflow")
    parser.add_argument("--only", help="comma-separated check names to run, e.g. hub_team,about")
    args = parser.parse_args()
    cases = [case for case in ROUTES if case.test in (check_hub_orbit, check_hub_orbit_v4, check_hub_samples, check_cache_pages, check_hub_map_loading_v41)] if args.orbit_only else None
    if args.lab_only:
        cases = [case for case in ROUTES if case.test in (check_ai_lab, check_lab_legacy_v41, check_ct_defense, check_team_fingerprint)]
    if args.samples:
        cases = [case for case in (cases if cases is not None else ROUTES) if case.test.__name__ not in REAL_DATA_ONLY]
    if args.only:
        names = {f"check_{name.strip().removeprefix('check_')}" for name in args.only.split(",")}
        cases = [case for case in (cases if cases is not None else ROUTES) if case.test.__name__ in names]
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    lineups = json.loads((root / "public/data/de_mirage/lineups.json").read_text(encoding="utf-8"))
    smoke = Smoke(args.base.rstrip("/"), lineups, args.shots, samples=args.samples)
    origin = urlsplit(smoke.base)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop = browser.new_context(viewport={"width": 1440, "height": 900})
            desktop.grant_permissions(["clipboard-read", "clipboard-write"],
                                      origin=f"{origin.scheme}://{origin.netloc}")
            run_routes(smoke, desktop, cases=cases)

            # The site is desktop-first; 375px overflow checks are opt-in.
            if args.mobile:
                mobile = browser.new_context(viewport={"width": 375, "height": 812})
                run_routes(smoke, mobile, mobile=True, cases=cases)

            smoke.check(not smoke.errors,
                        f"no console errors ({len(smoke.errors)}): {smoke.errors[:3]}")
        finally:
            browser.close()

    print(f"\n{'PASS' if not smoke.failures else 'FAIL'}: "
          f"{smoke.checks} checks, {len(smoke.failures)} failure(s)")
    return 1 if smoke.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
