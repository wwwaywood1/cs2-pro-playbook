import json
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "register_hltv_dates", Path(__file__).resolve().parents[1] / "scripts" / "register_hltv_dates.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _tree(tmp_path):
    raw = tmp_path / "raw"
    stem = "pgl-astana-2026-the-mongolz-vs-aurora-bo3-ABCDEFGHIJKLMNOPQRSTUV"
    folder = raw / "hltv" / stem
    folder.mkdir(parents=True)
    for name in ("the-mongolz-vs-aurora-m1-overpass.dem", "the-mongolz-vs-aurora-m2-mirage.dem",
                 "._the-mongolz-vs-aurora-m2-mirage.dem"):
        (folder / name).write_bytes(b"x")
    plan = {"matches": [{"demo_id": 107977, "hltv_match_id": 2394148, "unix_ms": 1778666400000,
                         "event": "PGL Astana 2026"},
                        {"demo_id": 999, "hltv_match_id": 1, "unix_ms": 1778666400000, "event": "X"}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "dl.log").write_text(
        "== start\nASSET logo.png\n"
        f"OK 107977 2394148 123456 {stem}.rar\n"
        "FAIL 5 6 http=403 file=\n"
        "OK 999 1 already-present some-other-archive.rar\n")
    (tmp_path / "events.json").write_text(json.dumps({"_note": "", "events": {}}))
    (tmp_path / "dates.csv").write_text("demo_id,date\n")
    return raw


def test_dry_run_changes_nothing(tmp_path, capsys):
    raw = _tree(tmp_path)
    args = ["--plan", str(tmp_path / "plan.json"), "--log", str(tmp_path / "dl.log"), "--raw", str(raw),
            "--dates", str(tmp_path / "dates.csv"), "--events", str(tmp_path / "events.json")]
    assert mod.main(args) == 0
    out = capsys.readouterr().out
    assert "games dated: 2" in out and "new events: 1" in out and "not imported yet" in out
    assert (tmp_path / "dates.csv").read_text() == "demo_id,date\n"


def test_apply_writes_exact_dates_and_event(tmp_path):
    raw = _tree(tmp_path)
    args = ["--plan", str(tmp_path / "plan.json"), "--log", str(tmp_path / "dl.log"), "--raw", str(raw),
            "--dates", str(tmp_path / "dates.csv"), "--events", str(tmp_path / "events.json"), "--apply"]
    assert mod.main(args) == 0
    rows = (tmp_path / "dates.csv").read_text().strip().splitlines()[1:]
    assert len(rows) == 2 and all(r.endswith(",2026-05-13") for r in rows)
    assert all(r.startswith("hltv-") for r in rows)
    ev = json.loads((tmp_path / "events.json").read_text())["events"]
    assert ev["pgl-astana-2026"]["start"] == "2026-05-13" and ev["pgl-astana-2026"]["source"] == "hltv-plan"
    # idempotent: a second run adds nothing
    assert mod.main(args) == 0
    assert len((tmp_path / "dates.csv").read_text().strip().splitlines()) == 3


def test_existing_conflicting_row_is_kept(tmp_path, capsys):
    raw = _tree(tmp_path)
    args = ["--plan", str(tmp_path / "plan.json"), "--log", str(tmp_path / "dl.log"), "--raw", str(raw),
            "--dates", str(tmp_path / "dates.csv"), "--events", str(tmp_path / "events.json"), "--apply"]
    mod.main(args)
    rows = (tmp_path / "dates.csv").read_text().splitlines()
    demo = rows[1].split(",")[0]
    (tmp_path / "dates.csv").write_text(f"demo_id,date\n{demo},2026-05-01\n")
    mod.main(args)
    out = capsys.readouterr().out
    assert "keeps 2026-05-01" in out
    assert f"{demo},2026-05-01" in (tmp_path / "dates.csv").read_text()
