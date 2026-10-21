"""Checked facts about a team on a map, compared with every other team on that map.

Each fact is a number with its sample, the baseline (all other teams' gun rounds on the
map) and a two-proportion z score, plus a short template sentence in Chinese and English.
Only differences that are both large (>= MIN_DIFF) and unlikely to be noise (|z| >= MIN_Z)
become facts; "signature" facts (most used recipe, lurker, default setup) need MIN_SHARE.
This is the base for written analysis and teaching: an LLM may later rephrase these
sentences, but every claim must come from a fact here (DESIGN.md › Roadmap M4).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import polars as pl

MIN_DIFF = 0.10
MIN_Z = 2.0
MIN_SHARE = 0.25
MIN_ROUNDS = 15

LABEL_ZH = {"fast": "快攻", "mid": "中期进攻", "late": "拖后进攻", "no_hit": "没打进包点",
            "A": "A 点", "B": "B 点"}
LABEL_EN = {"fast": "fast hits", "mid": "mid-round hits", "late": "late hits", "no_hit": "rounds without a hit",
            "A": "A", "B": "B"}


def _z(k1: int, n1: int, k2: int, n2: int) -> float:
    if not n1 or not n2:
        return 0.0
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se > 0 else 0.0


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def _compare(fid: str, side: str, k: int, n: int, k0: int, n0: int, zh: str, en: str, **extra) -> dict | None:
    if n < MIN_ROUNDS or not n0:
        return None
    share, base = k / n, k0 / n0
    z = _z(k, n, k0, n0)
    if abs(share - base) < MIN_DIFF or abs(z) < MIN_Z:
        return None
    more = share > base
    return {
        "id": fid, "side": side, "kind": "compare", "value": round(share, 3), "baseline": round(base, 3),
        "rounds": n, "z": round(z, 2), "direction": "more" if more else "less",
        "text": {
            "zh": f"{zh}占 {_pct(share)}，{'高于' if more else '低于'}其他队伍的 {_pct(base)}（{n} 个枪局）",
            "en": f"{en}: {_pct(share)} vs {_pct(base)} for other teams ({n} gun rounds)",
        },
        **extra,
    }


def _flag_rate(plans: pl.DataFrame, rest: pl.DataFrame, col: str, fid: str, zh: str, en: str) -> dict | None:
    a = plans.filter(pl.col("commit_s").is_not_null())
    b = rest.filter(pl.col("commit_s").is_not_null())
    if col == "fake_from":
        ka, kb = int(a["fake_from"].is_not_null().sum()), int(b["fake_from"].is_not_null().sum())
    else:
        ka, kb = int(a[col].sum()), int(b[col].sum())
    return _compare(fid, "T", ka, a.height, kb, b.height, zh, en)


def team_insights(team: str, plans: pl.DataFrame, ct: pl.DataFrame, recipes: list[dict],
                  spot_names: dict[str, dict]) -> list[dict]:
    """Facts for one team. plans/ct: all teams on the map (tactics.analyse_map output)."""
    p = plans.filter(pl.col("gun"))
    mine, rest = p.filter(pl.col("team") == team), p.filter(pl.col("team") != team)
    facts: list[dict | None] = []

    for tempo in ("fast", "late"):
        facts.append(_compare(f"t_tempo_{tempo}", "T", int((mine["tempo"] == tempo).sum()), mine.height,
                              int((rest["tempo"] == tempo).sum()), rest.height,
                              LABEL_ZH[tempo], LABEL_EN[tempo]))
    att_m, att_r = mine.filter(pl.col("attempt").is_not_null()), rest.filter(pl.col("attempt").is_not_null())
    for site in ("A", "B"):
        facts.append(_compare(f"t_site_{site}", "T", int((att_m["attempt"] == site).sum()), att_m.height,
                              int((att_r["attempt"] == site).sum()), att_r.height,
                              f"进攻 {site} 点的回合", f"Rounds going {site}"))
    facts.append(_flag_rate(mine, rest, "split", "t_split", "分兵进点", "Split hits"))
    facts.append(_flag_rate(mine, rest, "lurk", "t_lurk", "有人摸边的进攻", "Hits with a lurker"))
    facts.append(_flag_rate(mine, rest, "fake_from", "t_fake", "先假打再转点", "Fakes before the hit"))

    # signature recipe: the team's most used execute, if it is a real habit
    used = mine.filter(pl.col("recipe_id").is_not_null()).group_by("recipe_id").agg(
        n=pl.len(), won=pl.col("won").sum()).sort("n", "recipe_id", descending=[True, False])
    hits = mine.filter(pl.col("commit_s").is_not_null()).height
    if used.height and hits >= MIN_ROUNDS:
        rid, n, won = used.row(0)
        if n / hits >= MIN_SHARE * 0.5 and n >= 4:
            r = next(x for x in recipes if x["id"] == rid)
            parts_zh = " + ".join((spot_names.get(c["spot_id"]) or {}).get("zh") or c["label"] for c in r["core"])
            parts_en = " + ".join((spot_names.get(c["spot_id"]) or {}).get("en") or c["label"] for c in r["core"])
            facts.append({
                "id": "t_signature_recipe", "side": "T", "kind": "signature", "value": round(n / hits, 3),
                "rounds": hits, "recipe_id": rid, "won": int(won), "win_rate": round(won / n, 3),
                "text": {"zh": f"最常用的爆弹：{r['site']} 点 {parts_zh}（{n} 次，赢 {int(won)} 次）",
                         "en": f"Go-to execute: {r['site']} with {parts_en} ({n} times, won {int(won)})"},
            })

    lurks = mine.filter(pl.col("lurk").fill_null(False)).group_by("lurker_steamid").agg(
        n=pl.len(), name=pl.col("lurker_name").mode().sort().first()).sort("n", "name", "lurker_steamid", descending=[True, False, False])
    if lurks.height and hits >= MIN_ROUNDS:
        sid, n, name = lurks.row(0)
        if n / hits >= MIN_SHARE * 0.5 and n >= 4:
            facts.append({
                "id": "t_main_lurker", "side": "T", "kind": "signature", "value": round(n / hits, 3), "rounds": hits,
                "steamid": str(sid), "name": name,
                "text": {"zh": f"{name} 是最常摸边的人（{n} 次进攻时在另一侧或远离进攻点）",
                         "en": f"{name} is the usual lurker ({n} hits with him on the other side or far away)"},
            })

    # CT side
    c = ct.filter(pl.col("gun"))
    cm, cr = c.filter(pl.col("team") == team), c.filter(pl.col("team") != team)
    facts.append(_compare("ct_forward", "CT", int((cm["n_forward"] > 0).sum()), cm.height,
                          int((cr["n_forward"] > 0).sum()), cr.height, "开局有人前压的回合", "Rounds with an early push"))
    facts.append(_compare("ct_stack", "CT", int(cm["stack_site"].is_not_null().sum()), cm.height,
                          int(cr["stack_site"].is_not_null().sum()), cr.height, "堆点防守的回合", "Stacked rounds"))
    if cm.height >= MIN_ROUNDS:
        top = cm.group_by("shape_20s").agg(n=pl.len(), won=pl.col("won").sum()).drop_nulls("shape_20s").sort(
            "n", "shape_20s", descending=[True, False])
        if top.height:
            shape, n, won = top.row(0)
            if n / cm.height >= MIN_SHARE:
                facts.append({
                    "id": "ct_default_setup", "side": "CT", "kind": "signature", "value": round(n / cm.height, 3),
                    "rounds": cm.height, "shape": shape, "won": int(won), "win_rate": round(won / n, 3),
                    "text": {"zh": f"CT 默认站位 {shape}（开局 20 秒，{_pct(n / cm.height)} 的枪局，胜率 {_pct(won / n)}）",
                             "en": f"Default CT setup {shape} at 20 s ({_pct(n / cm.height)} of gun rounds, won {_pct(won / n)})"},
                })
    rot_m = cm.filter(pl.col("n_far").fill_null(0) > 0)
    rot_r = cr.filter(pl.col("n_far").fill_null(0) > 0)
    facts.append(_compare("ct_rotate", "CT", int((rot_m["n_rotated"] > 0).sum()), rot_m.height,
                          int((rot_r["n_rotated"] > 0).sum()), rot_r.height,
                          "进攻开始后有人及时回防的回合", "Rounds where a CT rotated in time"))
    return [f for f in facts if f]


def fingerprint(facts: list[dict]) -> str:
    """Identity of a team's fact list; scripts/insight_text.py stamps written summaries with it."""
    key = json.dumps([[f["id"], f["text"]["en"]] for f in facts], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def attach_summaries(teams: list[dict], path: Path) -> int:
    """Add the checked LLM paragraph (config/insight_text/<map>.json) to each team whose facts
    are unchanged since it was written. Stale or missing paragraphs are simply left out."""
    if not path.exists():
        return 0
    written = json.loads(path.read_text())
    n = 0
    for p in teams:
        w = written.get(p["slug"])
        if w and p.get("insights") and w.get("fingerprint") == fingerprint(p["insights"]):
            p["summary"] = {"zh": w["zh"], "en": w["en"], "facts": w["facts"]}
            n += 1
    return n
