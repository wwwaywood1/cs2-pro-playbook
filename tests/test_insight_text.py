"""LLM team summaries: the number guard and the stale-fact guard."""
import importlib.util
import json

from playbook.insights import attach_summaries, fingerprint
from playbook.config import ROOT

spec = importlib.util.spec_from_file_location("insight_text", ROOT / "scripts" / "insight_text.py")
it = importlib.util.module_from_spec(spec)
spec.loader.exec_module(it)

FACTS = [{"id": "t_split", "side": "T", "text": {"zh": "分兵进点占 87%，高于其他队伍的 61%（15 个枪局）",
                                                  "en": "Split hits: 87% vs 61% for other teams (15 gun rounds)"}}]


def setup(tmp_path, monkeypatch):
    site = tmp_path / "site" / "de_x" / "teams"
    site.mkdir(parents=True)
    (site / "aa.json").write_text(json.dumps({"slug": "aa", "team": "AA", "insights": FACTS}))
    monkeypatch.setattr(it, "SITE", tmp_path / "site")
    monkeypatch.setattr(it, "OUT", tmp_path / "out")


def test_fingerprints_match():
    assert it.fingerprint(FACTS) == fingerprint(FACTS)


def test_check_accepts_supported_numbers_and_rejects_invented(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    good = {"aa": {"zh": "AA 爱分兵：87% 的进攻分两路，联盟平均只有 61%。", "en": "AA love splits: 87% of hits vs 61% league-wide.",
                   "facts": ["t_split"]}}
    bad = {"aa": {"zh": "AA 分兵 90%。", "en": "AA split 90%.", "facts": ["t_split"]}}
    (tmp_path / "good.json").write_text(json.dumps(good))
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    assert it.check("de_x", tmp_path / "bad.json") == 1
    assert not (tmp_path / "out" / "de_x.json").read_text().strip("{}\n")
    assert it.check("de_x", tmp_path / "good.json") == 0
    saved = json.loads((tmp_path / "out" / "de_x.json").read_text())
    assert saved["aa"]["fingerprint"] == fingerprint(FACTS)


def test_attach_drops_stale(tmp_path):
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"aa": {"zh": "z", "en": "e", "facts": ["t_split"], "fingerprint": fingerprint(FACTS)}}))
    fresh = [{"slug": "aa", "insights": FACTS}]
    stale = [{"slug": "aa", "insights": [dict(FACTS[0], text={"zh": "x", "en": "changed"})]}]
    assert attach_summaries(fresh, path) == 1 and fresh[0]["summary"]["en"] == "e"
    assert attach_summaries(stale, path) == 0 and "summary" not in stale[0]


def test_attach_command_writes_the_site_files_like_the_export(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    team = tmp_path / "site" / "de_x" / "teams" / "aa.json"
    good = {"aa": {"zh": "AA 爱分兵：87% 的进攻分两路，联盟平均只有 61%。", "en": "AA love splits: 87% of hits vs 61% league-wide.",
                   "facts": ["t_split"]}}
    (tmp_path / "good.json").write_text(json.dumps(good))
    assert it.check("de_x", tmp_path / "good.json") == 0
    assert it.attach("de_x") == 1
    d = json.loads(team.read_text())
    assert d["summary"] == {"zh": good["aa"]["zh"], "en": good["aa"]["en"], "facts": ["t_split"]}
    assert "\n" not in team.read_text() and "爱分兵" in team.read_text()      # compact, not ASCII-escaped
    # facts changed since the paragraph was written: the stale paragraph comes off again
    d["insights"] = [dict(FACTS[0], text={"zh": "x", "en": "changed"})]
    team.write_text(json.dumps(d))
    assert it.attach("de_x") == 0 and "summary" not in json.loads(team.read_text())
