"""Exercise smoke mock dispatch and failure isolation without launching Chromium."""
import importlib.util
import inspect
import json
import shutil
import sys
from json import dumps
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class InterruptedCheck(Exception):
    pass


@pytest.fixture
def smoke_module(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    # Browser tooling is optional for pytest. Only stub the import; the checks
    # and their real mock handlers are executed below.
    api = ModuleType('playwright.sync_api')
    api.BrowserContext = api.Page = object
    api.expect = api.sync_playwright = None
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', api)
    spec = importlib.util.spec_from_file_location('smoke_under_test', root / 'web/e2e/smoke.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    module.__file__ = str(tmp_path / 'web/e2e/smoke.py')
    shutil.copytree(root / 'samples/site', tmp_path / 'web/public/data')
    return module


class MockPage:
    def __init__(self, failure):
        self.failure = failure
        self.handlers = []
        self.responses = {}

    def route(self, pattern, handler):
        self.handlers.append((pattern, handler))
        if self.failure == 'registration':
            raise InterruptedCheck('route setup interrupted')

    def unroute_all(self, **kwargs):
        self.handlers.clear()

    def reload(self):
        # Match Python Playwright's callback arity contract, including defaults.
        # A two-argument lambda receives Request as its second argument.
        for pattern, handler in list(self.handlers):
            request = SimpleNamespace(url='https://smoke.test/replay/smoke-fast/2.json')

            def fulfill(*, json, pattern=pattern):
                self.responses[pattern] = dumps(json)

            intercepted = SimpleNamespace(request=request, fulfill=fulfill)
            args = (intercepted, request)[:len(inspect.signature(handler).parameters)]
            handler(*args)
        raise InterruptedCheck('assertion interrupted')

    def locator(self, selector):
        return SimpleNamespace(count=lambda: 2)

    def emulate_media(self, **kwargs):
        pass

    def evaluate(self, *args):
        pass


@pytest.mark.parametrize('failure', ['registration', 'assertion'])
@pytest.mark.parametrize('name', [
    'tactics_linking', 'replay_switching', 'archive_replay', 'hub_entrance',
    'match_dates', 'team_shields', 'radar6',
])
def test_route_mocks_are_serializable_and_removed_after_failure(smoke_module, name, failure):
    module = smoke_module
    root = Path(module.__file__).parents[1] / 'public/data'
    lineups = json.loads((root / 'de_mirage/lineups.json').read_text())
    page = MockPage(failure)
    with pytest.raises(InterruptedCheck):
        getattr(module, f'check_{name}')(module.Smoke('https://smoke.test', lineups), page)
    assert not page.handlers, f'{name} leaked a network mock after {failure} failed'
    if name == 'match_dates' and failure == 'assertion':
        assert json.loads(page.responses['**/data/index.json'])['data_through'] == '2026-08-01'
        assert isinstance(json.loads(page.responses['**/data/heatmap_teams.json']), list)
        profile = json.loads(page.responses['**/data/de_mirage/teams/vitality.json'])
        assert len(profile['matches']) == 4


def test_failed_check_cannot_leave_a_dialog_or_cache_in_the_next_page(smoke_module, monkeypatch):
    module = smoke_module
    pages = []

    class Page:
        def __init__(self):
            self.closed = False
            self.contaminated = False

        def set_default_timeout(self, timeout):
            pass

        def close(self):
            self.closed = True

    def new_page():
        assert all(page.closed for page in pages)
        page = Page()
        pages.append(page)
        return page

    def check(smoke, case, page, **kwargs):
        assert not page.contaminated
        page.contaminated = True
        if case == 'failed':
            smoke.check(False, 'simulated UI failure with an open dialog')

    monkeypatch.setattr(module, 'ROUTES', ['failed', 'next'])
    monkeypatch.setattr(module, 'run_route', check)
    smoke = module.Smoke('https://smoke.test', [])
    monkeypatch.setattr(smoke, 'watch', lambda page: None)
    module.run_routes(smoke, SimpleNamespace(new_page=new_page))
    assert len(pages) == 2 and all(page.closed for page in pages)
    assert smoke.failures == ['simulated UI failure with an open dialog']
