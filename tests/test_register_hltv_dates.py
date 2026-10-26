import json
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "register_hltv_dates", Path(__file__).resolve().parents[1] / "scripts" / "register_hltv_dates.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

STEM = "pgl-astana-2026-the-mongolz-vs-aurora-bo3-ABCDEFGHIJKLMNOPQRSTUV"


def _tree(tmp_path, events=None):
    raw = tmp_path / "raw"
    folder = raw / "hltv" / STEM
    folder.mkdir(parents=True)
    for name in ("the-mongolz-vs-aurora-m1-overpass.dem", "the-mongolz-vs-aurora-m2-mirage.dem",
                 "._the-mongolz-vs-aurora-m2-mirage.dem"):
        (folder / name).write_bytes(b"x")
    plan = {"matches": [{"demo_id": 107977, "hltv_match_id": 2394148, "unix_ms": 1778666400000,
                         "event": "PGL Astana 2026", "maps_played": ["Overpass", "Mirage"]},
                        {"demo_id": 999, "hltv_match_id": 1, "unix_ms": 1778666400000, "event": "X"}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "dl.log").write_text(
        "== start\nASSET logo.png\n"
        f"OK 107977 2394148 123456 {STEM}.rar\n"
        "FAIL 5 6 http=403 file=\n"
        "OK 999 1 already-present some-other-archive.rar\n")
    (tmp_path / "events.json").write_text(json.dumps({"_note": "", "events": events or {}}))
    (tmp_path / "dates.csv").write_text("demo_id,date\n")
    return raw


def _args(tmp_path, raw, *extra):
    return ["--raw", str(raw), "--dates", str(tmp_path / "dates.csv"), "--events", str(tmp_path / "events.json"),
            "--registry", str(tmp_path / "registry.json"), *extra]


def _plan(tmp_path):
    return ["--plan", str(tmp_path / "plan.json"), "--log", str(tmp_path / "dl.log")]


def test_dry_run_changes_nothing(tmp_path, capsys):
    raw = _tree(tmp_path)
    assert mod.main(_args(tmp_path, raw, *_plan(tmp_path))) == 0
    out = capsys.readouterr().out
    assert "games dated: 2" in out and "new events: 1" in out and "not imported yet" in out
    assert (tmp_path / "dates.csv").read_text() == "demo_id,date\n"
    assert not (tmp_path / "registry.json").exists()


def test_apply_writes_exact_dates_event_and_registry(tmp_path):
    raw = _tree(tmp_path)
    args = _args(tmp_path, raw, *_plan(tmp_path), "--apply")
    assert mod.main(args) == 0
    rows = (tmp_path / "dates.csv").read_text().strip().splitlines()[1:]
    assert len(rows) == 2 and all(r.endswith(",2026-05-13") for r in rows)
    assert all(r.startswith("hltv-") for r in rows)
    ev = json.loads((tmp_path / "events.json").read_text())["events"]
    assert ev["pgl-astana-2026"]["start"] == "2026-05-13" and ev["pgl-astana-2026"]["source"] == "hltv-plan"
    reg = json.loads((tmp_path / "registry.json").read_text())
    assert reg["archives"][STEM] == "2394148" and reg["matches"]["2394148"]["maps"] == ["Overpass", "Mirage"]
    assert "some-other-archive" in reg["archives"]  # known from the log even though it is not imported
    # idempotent: a second run adds nothing
    assert mod.main(args) == 0
    assert len((tmp_path / "dates.csv").read_text().strip().splitlines()) == 3


def test_existing_conflicting_row_is_kept(tmp_path, capsys):
    raw = _tree(tmp_path)
    args = _args(tmp_path, raw, *_plan(tmp_path), "--apply")
    mod.main(args)
    rows = (tmp_path / "dates.csv").read_text().splitlines()
    demo = rows[1].split(",")[0]
    (tmp_path / "dates.csv").write_text(f"demo_id,date\n{demo},2026-05-01\n")
    mod.main(args)
    out = capsys.readouterr().out
    assert "keeps 2026-05-01" in out
    assert f"{demo},2026-05-01" in (tmp_path / "dates.csv").read_text()


def test_archives_mapping_backfill_and_registry_only_rerun(tmp_path, capsys):
    raw = _tree(tmp_path, events={"pgl-astana-2026": {"name": "PGL Astana 2026", "start": "2026-05-09",
                                                      "end": "2026-05-17"}})
    mapping = {f"{STEM}.rar": {"hltv_match_id": 2394148, "unix_ms": 1778666400000, "event": "PGL Astana 2026",
                               "maps": "Overpass,Mirage,Nuke"}}
    (tmp_path / "arch.json").write_text(json.dumps(mapping))
    assert mod.main(_args(tmp_path, raw, "--archives", str(tmp_path / "arch.json"), "--apply")) == 0
    assert len((tmp_path / "dates.csv").read_text().strip().splitlines()) == 3
    assert "new events: 0" in capsys.readouterr().out
    # registry-only run (no inputs) after another archive was imported dates nothing new and changes nothing
    (tmp_path / "dates.csv").write_text("demo_id,date\n")
    assert mod.main(_args(tmp_path, raw, "--apply")) == 0
    assert len((tmp_path / "dates.csv").read_text().strip().splitlines()) == 3


def test_map_mismatch_is_skipped(tmp_path, capsys):
    raw = _tree(tmp_path)
    mapping = {STEM: {"hltv_match_id": 2394148, "unix_ms": 1778666400000, "maps": ["Nuke", "Mirage"]}}
    (tmp_path / "arch.json").write_text(json.dumps(mapping))
    assert mod.main(_args(tmp_path, raw, "--archives", str(tmp_path / "arch.json"), "--apply")) == 0
    out = capsys.readouterr().out
    assert "skipped" in out and "games dated: 0" in out
    assert (tmp_path / "dates.csv").read_text() == "demo_id,date\n"


def test_registry_never_replaces_a_different_match(tmp_path, capsys):
    raw = _tree(tmp_path)
    (tmp_path / "registry.json").write_text(json.dumps({"matches": {"1": {
        "start_unix_ms": 1778666400000, "maps": []}}, "archives": {STEM: "1"}}))
    mapping = {STEM: {"hltv_match_id": 2394148, "unix_ms": 1778666400000}}
    (tmp_path / "arch.json").write_text(json.dumps(mapping))
    mod.main(_args(tmp_path, raw, "--archives", str(tmp_path / "arch.json"), "--apply"))
    assert "registry keeps match 1" in capsys.readouterr().out
    assert json.loads((tmp_path / "registry.json").read_text())["archives"][STEM] == "1"


def test_clamp_to_event_range():
    events = {"x": {"start": "2026-06-01", "end": "2026-06-07"}}
    assert mod.clamp_to_event("2026-06-08", "x", events) == "2026-06-07"
    assert mod.clamp_to_event("2026-05-31", "x", events) == "2026-06-01"
    assert mod.clamp_to_event("2026-06-09", "x", events) == "2026-06-09"
    assert mod.clamp_to_event("2026-06-08", "unknown", events) == "2026-06-08"


def test_game_map_parsing():
    assert mod.game_map(Path("a-vs-b-m1-dust2.dem")) == "dust2"
    assert mod.game_map(Path("a-vs-b-m3-ancient-p2.dem")) == "ancient"
    assert mod.game_map(Path("weird.dem")) is None


def test_dataset_tree_dated_by_match_id(tmp_path, capsys):
    raw = _tree(tmp_path)
    folder = raw / "cs2povarchive" / "cac2026" / "2394199-legacy-vs-nrg"
    folder.mkdir(parents=True)
    (folder / "legacy-vs-nrg-nuke.dem").write_bytes(b"x")
    (tmp_path / "starts.json").write_text(json.dumps({"2394199": {"unix_ms": 1779255300000, "maps": ["Nuke"]},
                                                      "1": {"unix_ms": 1779255300000}}))
    assert mod.main(_args(tmp_path, raw, "--matches", str(tmp_path / "starts.json"), "--apply")) == 0
    rows = (tmp_path / "dates.csv").read_text().strip().splitlines()[1:]
    assert rows == ["2394199_legacy-vs-nrg-nuke,2026-05-20"]
