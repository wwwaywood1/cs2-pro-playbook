"""Demos on another disk than the temp folder are parsed from local copies (playbook.parse)."""
from pathlib import Path

from playbook import parse


def test_local_demos_are_read_in_place(tmp_path):
    demo = tmp_path / "a-vs-b-m1-mirage.dem"
    demo.write_bytes(b"demo")
    with parse.readable_copies([demo]) as files:
        assert files == [demo]


def test_demos_on_another_disk_are_copied_with_their_names(tmp_path, monkeypatch):
    parts = [tmp_path / "a-vs-b-m2-nuke-p1.dem", tmp_path / "a-vs-b-m2-nuke-p2.dem"]
    for i, p in enumerate(parts):
        p.write_bytes(b"part%d" % i)
    monkeypatch.setattr(parse, "same_device", lambda path, folder: False)
    with parse.readable_copies(parts) as files:
        assert [f.name for f in files] == [p.name for p in parts]
        assert all(f.parent != tmp_path and f.read_bytes() == p.read_bytes() for f, p in zip(files, parts))
        copies = list(files)
    assert not any(f.exists() for f in copies)        # removed afterwards
    assert all(p.exists() for p in parts)


def test_parse_demo_keeps_the_original_identity(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / "hltv" / "event-a-vs-b-bo3-X"
    raw.mkdir(parents=True)
    demo = raw / "a-vs-b-m1-mirage.dem"
    demo.write_bytes(b"demo")
    monkeypatch.setattr(parse, "same_device", lambda path, folder: False)
    seen = {}

    def fake(paths, files, aliases, verbose):
        seen.update(paths=paths, files=files, ident=parse.demo_identity(paths[0]))
        return {}

    monkeypatch.setattr(parse, "_parse_demo", fake)
    parse.parse_demo(demo)
    assert seen["paths"] == [demo] and seen["files"][0] != demo
    assert seen["ident"]["demo_id"].startswith("hltv-") and seen["ident"]["demo_id"].endswith("_a-vs-b-m1-mirage")
