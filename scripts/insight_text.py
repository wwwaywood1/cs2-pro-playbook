"""Natural-language team summaries written by an LLM from checked facts, with a number guard.

    python scripts/insight_text.py brief de_mirage            # data/site -> delegation/inputs/insights/de_mirage.json
    python scripts/insight_text.py check de_mirage reply.json # validate -> config/insight_text/de_mirage.json

The LLM sees only the facts of playbook/insights.py (each a template sentence with its numbers)
and returns, per team, one short paragraph in Chinese and English plus the fact ids it used.
`check` rejects any paragraph that cites an unknown fact or contains a number that does not
appear in the cited facts, so the site never shows a figure that the data does not support.
Accepted paragraphs carry a fingerprint of their facts; export drops them once the facts change.
Standard library only (Python 3.9+), so it runs on any machine with the exported data.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "data" / "site"
BRIEFS = ROOT / "delegation" / "inputs" / "insights"
OUT = ROOT / "config" / "insight_text"
NUM = re.compile(r"\d+(?:\.\d+)?")
MAX_CHARS = {"zh": 160, "en": 360}


def fingerprint(facts: list) -> str:
    key = json.dumps([[f["id"], f["text"]["en"]] for f in facts], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def load_teams(m: str) -> dict:
    teams = {}
    for p in sorted((SITE / m / "teams").glob("*.json")):
        d = json.loads(p.read_text())
        if d.get("insights"):
            teams[d["slug"]] = d
    return teams


def brief(m: str) -> Path:
    rows = [{"slug": s, "team": d["team"], "n_matches": d.get("n_matches"),
             "facts": [{"id": f["id"], "side": f["side"], "zh": f["text"]["zh"], "en": f["text"]["en"]}
                       for f in d["insights"]]}
            for s, d in load_teams(m).items()]
    BRIEFS.mkdir(parents=True, exist_ok=True)
    path = BRIEFS / f"{m}.json"
    path.write_text(json.dumps({"map": m, "teams": rows}, ensure_ascii=False, indent=1))
    print(f"{len(rows)} teams -> {path}")
    return path


def allowed_numbers(facts: list) -> set:
    nums = set()
    for f in facts:
        for lang in ("zh", "en"):
            nums.update(NUM.findall(f["text"][lang]))
    return nums


def check(m: str, reply_path: str) -> int:
    teams = load_teams(m)
    reply = json.loads(Path(reply_path).read_text())
    reply = reply.get("teams", reply)
    accepted, problems = {}, []
    for slug, entry in reply.items():
        d = teams.get(slug)
        if d is None:
            problems.append(f"{slug}: unknown team")
            continue
        by_id = {f["id"]: f for f in d["insights"]}
        used = entry.get("facts") or []
        bad_ids = [i for i in used if i not in by_id]
        if not used or bad_ids:
            problems.append(f"{slug}: cites no facts or unknown ids {bad_ids}")
            continue
        ok = allowed_numbers([by_id[i] for i in used])
        errs = []
        for lang in ("zh", "en"):
            text = (entry.get(lang) or "").strip()
            if not text:
                errs.append(f"{lang} missing")
                continue
            # team names such as "9z" or "B8" carry digits of their own
            scrubbed = text.replace(d["team"], " ")
            extra = [n for n in NUM.findall(scrubbed) if n not in ok]
            if extra:
                errs.append(f"{lang} numbers not in facts: {extra}")
            if len(text) > MAX_CHARS[lang]:
                errs.append(f"{lang} too long ({len(text)} > {MAX_CHARS[lang]})")
        if errs:
            problems.append(f"{slug}: " + "; ".join(errs))
            continue
        accepted[slug] = {"zh": entry["zh"].strip(), "en": entry["en"].strip(), "facts": used,
                          "fingerprint": fingerprint(d["insights"])}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{m}.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(accepted)
    path.write_text(json.dumps(dict(sorted(old.items())), ensure_ascii=False, indent=1) + "\n")
    missing = sorted(set(teams) - set(old))
    print(f"{m}: accepted {len(accepted)}, rejected {len(problems)}, still missing {len(missing)} -> {path}")
    for p in problems:
        print("  REJECT", p)
    if missing:
        print("  missing:", " ".join(missing))
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("brief", "check"):
        sys.exit(__doc__)
    if sys.argv[1] == "brief":
        for m in sys.argv[2:]:
            brief(m)
    else:
        sys.exit(check(sys.argv[2], sys.argv[3]))
