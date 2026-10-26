"""The manual HLTV download flow: saved pages -> plan -> a page the owner clicks through -> refresh."""
import importlib.util
import json
import os
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from playbook import hltv

REPO = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "hltv"
COLOGNE_ARCHIVE = "iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(mid, demo, stars=2, event="PGL Masters Bucharest 2026"):
    return {"hltv_match_id": mid, "demo_id": demo, "unix_ms": 1792933200000, "event": event, "hltv_event_id": None,
            "teams": ["G2", "Aurora"], "maps_played": [], "stars": stars, "slug": f"g2-vs-aurora-m{mid}"}


def _repo(tmp_path):
    """Matches 100 (extracted archive), 101 (archive in the archive dir) and 102 (dataset folder)
    are here; 103 is registered but its archive is not."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    ssd = tmp_path / "ssd" / "archives"
    ssd.mkdir(parents=True)
    (root / "config" / "storage.toml").write_text(f'[archive]\ndir = "{ssd.as_posix()}"\n')
    (root / "config" / "hltv_archives.json").write_text(json.dumps({"archives": {
        "pgl-g2-vs-aurora-bo3-AAAAAAAAAAAAAAAAAAAA": "100", "pgl-g2-vs-aurora-bo3-BBBBBBBBBBBBBBBBBBBB": "101",
        "pgl-g2-vs-aurora-bo3-CCCCCCCCCCCCCCCCCCCC": "103"}}))
    (root / "data" / "raw" / "hltv" / "pgl-g2-vs-aurora-bo3-AAAAAAAAAAAAAAAAAAAA").mkdir(parents=True)
    (ssd / "pgl-g2-vs-aurora-bo3-BBBBBBBBBBBBBBBBBBBB.rar").write_bytes(b"r")
    (root / "data" / "raw" / "bo3gg" / "pgl-masters-bucharest-2026" / "102-g2-vs-aurora").mkdir(parents=True)
    return root


def _rows(html):
    """data-key -> the rest of its table row, in page order."""
    return dict(re.findall(r'<tr data-key="(m\d+)"(.*?)</tr>', html, flags=re.S))


def test_page_follows_the_queue_links_demos_and_greys_out_what_is_here(tmp_path):
    root = _repo(tmp_path)
    sync = root / "_sync"
    sync.mkdir()
    matches = [_entry(m, 9000 + m) for m in (100, 101, 102, 103)] + [_entry(104, None, event="A & B <Major>"),
                                                                     _entry(105, 9105)]
    (sync / "aurora_plan.json").write_text(json.dumps({"team": {"slug": "aurora"}, "matches": matches}))
    (sync / "aurora_queue.txt").write_text("9103 103\n9100 100\n- 104\n9101 101\n9102 102\n")
    page, total, here = hltv.write_queue_page("aurora", sync, root)
    assert (page, total, here) == (sync / "aurora_queue.html", 5, 3)
    html = page.read_text(encoding="utf-8")
    rows = _rows(html)
    assert list(rows) == ["m103", "m100", "m104", "m101", "m102"]       # queue order; 105 is not queued
    assert [k for k, r in rows.items() if 'class="have"' in r] == ["m100", "m101", "m102"]
    assert 'href="https://www.hltv.org/download/demo/9103"' in rows["m103"] and "下载 demo" in rows["m103"]
    assert "/download/demo/" not in rows["m104"]                          # demo unknown: link the match page
    assert 'href="https://www.hltv.org/matches/104/g2-vs-aurora-m104"' in rows["m104"]
    assert "A &amp; B &lt;Major&gt;" in rows["m104"]
    assert "★★" in rows["m103"] and "2026-10-25" in rows["m103"] and "13:00 UTC" in rows["m103"]
    assert hltv.PAGE_NOTE in html and "共 5 场 · 已有 3 场 · 待下载 2 场" in html


def test_page_is_self_contained_and_only_links_to_hltv_pages():
    html = hltv.queue_html("aurora", [_entry(1, 2), _entry(3, None)], set())
    assert not re.search(r"<(script|img|link|iframe|embed|object)\b[^>]*\b(src|href|data)=", html)
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert set(re.findall(r'href="([^"]+)"', html)) == {
        "https://www.hltv.org/download/demo/2", "https://www.hltv.org/matches/1/g2-vs-aurora-m1",
        "https://www.hltv.org/matches/3/g2-vs-aurora-m3"}
    storage = [line for line in html.split("<script>")[1].splitlines() if "localStorage" in line]
    assert storage and all("try {" in line for line in storage)      # every storage access is guarded
    assert "a:visited" in html


def test_ambiguous_matches_are_listed_separately_to_check():
    html = hltv.queue_html("aurora", [_entry(1, 2)], set(), [_entry(7, None)])
    queue, _, check = html.partition("待确认")
    assert 'data-key="m7"' not in queue and 'data-key="m7"' in check
    assert "https://www.hltv.org/matches/7/g2-vs-aurora-m7" in check


def test_queue_order_and_lines_missing_from_the_plan():
    plan = {"matches": [_entry(1, 11), _entry(2, None)]}
    assert [e["hltv_match_id"] for e in hltv.queue_entries(plan, None)] == [1, 2]   # no queue file
    entries = hltv.queue_entries(plan, hltv.read_queue("22 2\n33 3\nnot a line\n"))
    assert [(e["hltv_match_id"], e["demo_id"]) for e in entries] == [(2, 22), (3, 33)]


def test_page_says_so_when_the_drive_is_not_mounted(tmp_path):
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "data" / "raw").symlink_to(tmp_path / "Volumes" / "My PSSD" / "raw")
    sync = tmp_path / "sync"
    sync.mkdir()
    (sync / "t_plan.json").write_text(json.dumps({"matches": [_entry(1, 2)]}))
    page, total, here = hltv.write_queue_page("t", sync, root)
    assert (total, here) == (1, 0) and "外置硬盘没有连接" in page.read_text(encoding="utf-8")


def test_hltv_queue_script(tmp_path, monkeypatch, capsys):
    mod = _load("hltv_queue")
    root = _repo(tmp_path)
    monkeypatch.setattr(mod, "ROOT", root)
    sync = root / "_sync"
    sync.mkdir()
    assert mod.main(["aurora", "--sync-dir", str(sync)]) == 1                     # no plan yet
    (sync / "aurora_plan.json").write_text(json.dumps({"matches": [_entry(100, 9100), _entry(104, None)]}))
    assert mod.main(["aurora", "--sync-dir", str(sync)]) == 0
    assert "2 match(es), 1 already here, 1 to download" in capsys.readouterr().out
    assert 'data-key="m104"' in (sync / "aurora_queue.html").read_text(encoding="utf-8")


def _webarchive(path, html, url):
    """What Safari's File > Save As writes by default."""
    path.write_bytes(plistlib.dumps({"WebMainResource": {
        "WebResourceData": html.encode("utf-8"), "WebResourceURL": url, "WebResourceMIMEType": "text/html",
        "WebResourceTextEncodingName": "UTF-8", "WebResourceFrameName": ""}}, fmt=plistlib.FMT_BINARY))


def test_hltv_plan_from_saved_pages_writes_plan_queue_and_page(tmp_path, monkeypatch, capsys):
    mod = _load("hltv_plan")
    root = tmp_path / "repo"
    (root / "data" / "raw" / "hltv" / COLOGNE_ARCHIVE).mkdir(parents=True)
    monkeypatch.setattr(mod, "ROOT", root)
    saved = tmp_path / "saved"
    (saved / "matches").mkdir(parents=True)
    _webarchive(saved / "Results.webarchive", (FIX / "results.html").read_text(),
                "https://www.hltv.org/results?team=11861")
    (saved / "matches" / "G2 vs. Aurora at PGL Masters Bucharest 2026 | HLTV.org.html").write_text(
        '<html><head><link rel="canonical" href="https://www.hltv.org/matches/2399731/'
        'g2-vs-aurora-pgl-masters-bucharest-2026"></head>'
        '<body><a data-demo-link="/download/demo/113185">GOTV Demo</a></body></html>')
    out = tmp_path / "sync"
    assert mod.main(["aurora", "--results-html", str(saved / "Results.webarchive"),
                     "--match-html-dir", str(saved / "matches"), "--out-dir", str(out)]) == 0
    plan = json.loads((out / "aurora_plan.json").read_text())
    assert [(m["hltv_match_id"], m["demo_id"]) for m in plan["matches"]] == [(2399731, 113185), (2396562, None)]
    assert plan["matches"][1]["fmt"] == "cch" and "ambiguous" not in plan
    assert (out / "aurora_queue.txt").read_text() == "113185 2399731\n- 2396562\n"
    html = (out / "aurora_queue.html").read_text(encoding="utf-8")
    assert "https://www.hltv.org/download/demo/113185" in html
    assert "https://www.hltv.org/matches/2396562/big-vs-aurora-esports-world-cup-2026" in html
    printed = capsys.readouterr().out
    assert "2 to download (1 via their match page), 1 already have, 0 ambiguous, 1 not tier-1" in printed
    assert "Next: open" in printed


def _results_page(rows):
    return "".join(
        f'<div class="result-con" data-zonedgrouping-entry-unix="{unix}"><a href="/matches/{mid}/'
        f'aurora-vs-spirit-iem-cologne-major-2026"><div class="team">Aurora</div><div class="team">Spirit</div>'
        f'<span class="event-name">IEM Cologne Major 2026</span><div class="stars"><i></i></div>'
        f'<div class="map-text">bo3</div></a></div>' for mid, unix in rows)


def test_hltv_plan_lists_a_rematch_it_cannot_attribute(tmp_path, monkeypatch, capsys):
    mod = _load("hltv_plan")
    root = tmp_path / "repo"
    (root / "data" / "raw" / "hltv" / COLOGNE_ARCHIVE).mkdir(parents=True)   # one archive, two matches
    monkeypatch.setattr(mod, "ROOT", root)
    results = tmp_path / "results.html"
    results.write_text(_results_page([(2, 1781395131000), (1, 1781295131000)]))
    out = tmp_path / "sync"
    assert mod.main(["aurora", "--results-html", str(results), "--out-dir", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "0 to download" in printed and "2 ambiguous" in printed
    assert "https://www.hltv.org/matches/2/aurora-vs-spirit-iem-cologne-major-2026" in printed
    plan = json.loads((out / "aurora_plan.json").read_text())
    assert plan["matches"] == [] and [m["hltv_match_id"] for m in plan["ambiguous"]] == [2, 1]
    assert (out / "aurora_queue.txt").read_text() == ""
    assert "待确认" in (out / "aurora_queue.html").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_refresh_counts_only_moved_archives_and_registers_every_plan(tmp_path):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "refresh.sh", root / "scripts" / "refresh.sh")
    venv = root / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$PY_LOG"\n')   # every python step: log only
    (venv / "python").chmod(0o755)
    shims = tmp_path / "bin"   # macOS mv: "mv -n" skips a taken name silently and still exits 0
    shims.mkdir()
    (shims / "mv").write_text('#!/bin/bash\nif [ "$1" = -n ]; then\n  t="$3"; [ -d "$t" ] && t="$t/${2##*/}"\n'
                              f'  [ -e "$t" ] && exit 0\n  shift\nfi\nexec {shutil.which("mv")} "$@"\n')
    (shims / "mv").chmod(0o755)
    downloads = tmp_path / "home" / "Downloads"
    downloads.mkdir(parents=True)
    new = "iem-cologne-major-2026-aurora-vs-spirit-bo3-AAAAAAAAAAAAAAAAAAAA.rar"
    taken = "iem-cologne-major-2026-aurora-vs-g2-bo3-BBBBBBBBBBBBBBBBBBBB.rar"
    single = "esports-world-cup-2026-vitality-vs-mouz-nuke-CCCCCCCCCCCCCCCCCCCC.zip"
    for name in (new, taken, single):
        (downloads / name).write_bytes(b"new")
    hltv_raw = root / "data" / "raw" / "hltv"
    hltv_raw.mkdir(parents=True)
    (hltv_raw / taken).write_bytes(b"old")
    (root / "_sync").mkdir()
    for name in ("aurora_plan.json", "g2_plan.json", "g2_download.log"):
        (root / "_sync" / name).write_text("{}")
    env = {**os.environ, "HOME": str(tmp_path / "home"), "PY_LOG": str(tmp_path / "py.log"),
           "PATH": f"{shims}{os.pathsep}{os.environ.get('PATH', '')}"}
    proc = subprocess.run([shutil.which("bash"), str(root / "scripts" / "refresh.sh")], env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "== moved 2 archive(s) from ~/Downloads; 1 already present in data/raw/hltv" in proc.stdout
    assert f"already in data/raw/hltv, left in ~/Downloads: {taken}" in proc.stdout
    assert (downloads / taken).read_bytes() == b"new" and (hltv_raw / taken).read_bytes() == b"old"
    assert (hltv_raw / new).exists() and (hltv_raw / single).exists()
    calls = (tmp_path / "py.log").read_text().splitlines()
    assert "scripts/register_hltv_dates.py --plan _sync/aurora_plan.json --apply" in calls      # no log needed
    assert "scripts/register_hltv_dates.py --plan _sync/g2_plan.json --log _sync/g2_download.log --apply" in calls
    assert calls.index("scripts/archive_downloads.py --apply") < calls.index("scripts/hltv_queue.py aurora")
    assert "scripts/hltv_queue.py g2" in calls


def test_nothing_in_the_hltv_tooling_contacts_hltv():
    mod = _load("hltv_plan")
    with pytest.raises(SystemExit):
        mod.main(["aurora", "--fetch"])
    for name in ("scripts/hltv_plan.py", "scripts/hltv_queue.py", "playbook/hltv.py"):
        source = (REPO / name).read_text(encoding="utf-8")
        for word in ("urlopen", "http.client", "import requests", "subprocess", "curl", "webbrowser"):
            assert word not in source, f"{name} mentions {word}"
    assert not (REPO / "scripts" / "hltv_download.sh").exists()
