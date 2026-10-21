"""Analysis review: malformed events, transfers, floors, clustering and export parity."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import polars as pl
import pytest

from test_heatmap import MM, MM2, SID, tables
from test_tactics import MM as TMM, _round
from playbook.heatmap import clean_frames, build_heatmaps, roster_order, merge_phases, to_array
from playbook.export import heatmap_team_index
from playbook.semantics import round_plants
from playbook.tactics import (_neighbours, density_clusters, average_linkage, jaccard_matrix,
                             t_plans, landing_spots, execute_recipes, ct_summary)
from playbook.zones import _holds, make_summarizer

ASSIGN = pl.DataFrame(schema={"demo_id": pl.String, "nade_id": pl.UInt32, "spot_id": pl.String})


def plan(sub):
    return t_plans(sub, TMM, ASSIGN, {"A": (2000., 2000., 0.), "B": (0., 0., 0.)}).row(0, named=True)


def test_gun_filter_uses_each_event_owners_team_and_null_is_excluded():
    sub = tables(buy="eco")
    f = clean_frames(sub, MM)
    assert f["kills"].height == 0 and f["deaths"].height == 1
    sub["kills"] = sub["kills"].with_columns(victim_team=pl.lit(None, dtype=pl.String))
    assert clean_frames(sub, MM)["deaths"].is_empty()


def test_duplicate_team_rounds_fail_instead_of_multiplying_events():
    sub = tables()
    sub["team_rounds"] = pl.concat([sub["team_rounds"], sub["team_rounds"].head(1)])
    with pytest.raises(pl.exceptions.ComputeError, match="validation"):
        clean_frames(sub, MM)


def test_transferred_player_has_separate_grids_denominators_and_index_entries():
    a, b = tables(), tables()
    for key, frame in b.items():
        frame = frame.with_columns(demo_id=pl.lit("e"))
        for col in ("team", "attacker_team", "thrower_team"):
            if col in frame.columns:
                frame = frame.with_columns(pl.col(col).replace({"Red": "Green"}))
        if key == "positions":
            frame = frame.with_columns(x=pl.col("x") + 100)
        b[key] = frame
    sub = {key: pl.concat([a[key], b[key]]) for key in a}
    order = roster_order(sub["player_rounds"])
    hm = build_heatmaps(sub, MM, order)
    for slug in ("red", "green"):
        assert hm["teams"][slug]["roster"][0]["rounds"]["T"] == 1
        assert hm["teams"][slug]["players"][str(SID)]["per_round"]["T"]["all"]["presence"] == 4
    assert hm["teams"]["red"]["players"][str(SID)]["data"] != hm["teams"]["green"]["players"][str(SID)]["data"]
    index = heatmap_team_index(sub["player_rounds"], order, {t: [] for t in order})
    assert {r["team"] for r in index if str(SID) in [p["steamid"] for p in r["roster"]]} == {"Red", "Green"}


def test_first_live_plant_ignores_preround_postround_and_second_plant():
    sub = tables()
    sub["team_rounds"] = sub["team_rounds"].with_columns(dur_s=pl.lit(12.))
    sub["plants"] = pl.DataFrame({"demo_id": ["d"] * 4, "round_num": [1]*4,
                                  "site": ["A", "B", "A", "B"], "t_s": [-1., 8., 10., 15.]},
                                 schema_overrides={"round_num": pl.Int32})
    assert round_plants(sub).select("plant_site", "plant_t_s").rows() == [("B", 8.)]
    assert clean_frames(sub, MM)["presence"]["phase"].to_list() == ["early"]*3+["post"]
    sub["plants"] = sub["plants"].filter(pl.col("t_s") > 12)
    assert round_plants(sub).is_empty()
    assert clean_frames(sub, MM)["presence"]["phase"].to_list() == ["early"]*4


def test_holding_counts_vertical_motion_and_does_not_bridge_dead_sample():
    sub = tables()
    sub["positions"] = sub["positions"].with_columns(z=pl.Series([0., 100., 100., 100., 100.]),
                                                    alive=pl.Series([True, True, False, True, True]))
    p = clean_frames(sub, MM)["presence"]
    assert p.filter(pl.col("t_s").is_in([5, 7]))["holding"].to_list() == [False, False]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), None])
def test_nonfinite_coordinates_are_dropped_without_cast_crash(value):
    sub = tables()
    sub["shots"] = sub["shots"].with_columns(y=pl.lit(value, dtype=pl.Float64))
    assert clean_frames(sub, MM)["shots"].is_empty()


def test_preround_kills_and_utility_are_not_counted():
    sub = tables()
    sub["kills"] = sub["kills"].with_columns(t_s=pl.lit(-1.))
    sub["utility"] = sub["utility"].with_columns(throw_t_s=pl.lit(-1.))
    frames = clean_frames(sub, MM)
    assert all(frames[k].is_empty() for k in ("kills", "deaths", "utility"))


def test_holds_and_landing_spots_never_merge_across_floors():
    upper = clean_frames(tables(z=-99.), MM2)["presence"].filter(pl.col("holding"))
    lower = clean_frames(tables(z=-101.), MM2)["presence"].filter(pl.col("holding"))
    p = pl.concat([upper, lower, upper, lower])
    holds = _holds(p, 1)
    assert {h["level"] for h in holds} == {0, 1}
    assert all(h["seconds_per_round"] == 6 for h in holds)
    util = pl.DataFrame([dict(demo_id=f"d{i%2}", nade_id=i, is_post_round=False, thrower_side="T", type="smoke",
                              land_x=100., land_y=924., land_z=z, land_place="Spot", pop_t_s=10.)
                         for i,z in enumerate([-99.]*4+[-101.]*4)], schema_overrides={"nade_id": pl.UInt32})
    spots, assignment = landing_spots(util, MM2)
    assert spots.height == 2 and assignment.height == 8
    # Summary spot must expose the same level as the landing library and heat grid.
    sub = tables(z=-101.)
    sp = spots.filter(pl.col("z") == -101.)
    ass = pl.DataFrame({"demo_id": ["d"], "nade_id": [7], "spot_id": sp["spot_id"].to_list()}, schema_overrides={"nade_id": pl.UInt32})
    summary = make_summarizer(MM2, spots, ass)(clean_frames(sub, MM2), "Red", SID, "T", 1)
    assert summary["utility"]["spots"][0]["level"] == 1


def test_density_neighbours_keep_self_and_nearby_points_at_large_offsets():
    pts = np.array([[1e12, 1e12, 1e12], [1e12+1, 1e12, 1e12], [1e12+10, 1e12, 1e12]])
    assert [n.tolist() for n in _neighbours(pts, 2)] == [[0, 1], [0, 1], [2]]
    assert [n.tolist() for n in _neighbours(pts, 0)] == [[0], [1], [2]]


def test_density_tied_overlapping_seeds_are_permutation_invariant():
    pts = np.array([[0.,0,0], [1.,0,0], [2.,0,0], [3.,0,0]])
    expected = density_clusters(pts, 1.1, 2)
    for perm in ([3,2,1,0], [1,3,0,2], [2,0,3,1]):
        got = density_clusters(pts[perm], 1.1, 2)
        assert np.array_equal(got[np.argsort(perm)], expected)


def same_partition(a, b):
    return np.array_equal(a[:,None] == a, b[:,None] == b)


def test_average_linkage_scipy_random_jaccard_and_tie_disagreements(record_property):
    hierarchy = pytest.importorskip("scipy.cluster.hierarchy")
    spatial = pytest.importorskip("scipy.spatial.distance")
    rng = np.random.default_rng(2)
    mismatches = []
    for trial in range(300):
        sets = [frozenset(np.flatnonzero(rng.random(20) < .3)) for _ in range(12)]
        d = jaccard_matrix(sets)
        a = average_linkage(d, .6)
        b = hierarchy.fcluster(hierarchy.linkage(spatial.squareform(d), method="average"), .6, criterion="distance")
        if not same_partition(a, b):
            mismatches.append(trial)
            # Verify every partition returned is an actual average-linkage cut,
            # with ties handled by our documented row-major pair order.
            groups = [{i} for i in range(len(d))]
            had_tie = False
            while len(groups) > 1:
                pairs = [(float(d[np.ix_(sorted(x), sorted(y))].mean()), i, j)
                         for i,x in enumerate(groups) for j,y in enumerate(groups) if i < j]
                distance, i, j = min(pairs)
                if distance > .6:
                    break
                had_tie |= sum(abs(v-distance) < 1e-14 for v,_,_ in pairs) > 1
                groups[i] |= groups.pop(j)
            reference = np.zeros(len(d), dtype=int)
            for i,g in enumerate(groups):
                reference[list(g)] = i
            assert had_tie and same_partition(a, reference)
    # Seeded evidence is recorded in REVIEW-02; compare rather than require SciPy's tie rule.
    record_property("scipy_partition_mismatches", mismatches)


@pytest.mark.parametrize("plant_site,plant_time,nplayers,expected", [
    ("B", 35., 2, ("B", 35., "fast", "B")),
    ("A", 35., 1, ("A", 35., "fast", "A")),
    (None, None, 1, (None, None, "no_hit", None)),
])
def test_target_plant_overrides_earlier_touch_and_single_player_plant(plant_site, plant_time, nplayers, expected):
    sub = _round([(2800.,2000.)]*nplayers)
    sub["team_rounds"] = sub["team_rounds"].with_columns(plant_site=pl.lit(plant_site, dtype=pl.String), plant_t_s=pl.lit(plant_time, dtype=pl.Float64))
    got = plan(sub)
    assert tuple(got[k] for k in ("target", "commit_s", "tempo", "attempt")) == expected


def test_short_overtime_round_attempt_and_reentry_are_consistent():
    sub = _round([(2800.,2000.), (2000.,2800.)], plant_t=None)
    for k in ("team_rounds", "positions", "utility"):
        sub[k] = sub[k].with_columns(round_num=pl.lit(28, dtype=pl.Int32))
    sub["positions"] = sub["positions"].filter(pl.col("t_s") < 20)
    sub["team_rounds"] = sub["team_rounds"].with_columns(exec_lane=pl.lit("B"), exec_n_util=pl.lit(3))
    got = plan(sub)
    assert (got["target"], got["commit_s"], got["tempo"], got["attempt"]) == (None, None, "no_hit", "B")
    sub = _round([(2800.,2000.), (2000.,2800.)])
    sub["positions"] = sub["positions"].with_columns(pl.when(pl.col("t_s") == 32).then(pl.lit("A_APPROACH")).otherwise(pl.col("region")).alias("region"))
    assert plan(sub)["n_entries"] == 2


def test_duplicate_position_is_not_two_attackers():
    sub = _round([(2800.,2000.)], plant_t=None)
    sub["positions"] = pl.concat([sub["positions"], sub["positions"]])
    assert plan(sub)["commit_s"] is None


def test_early_commit_lurk_does_not_look_into_future():
    sub = _round([(2800.,2000.)], plant_t=5.)
    sub["positions"] = sub["positions"].with_columns(pl.when(pl.col("t_s") == 15).then(pl.lit("B")).otherwise(pl.col("lane")).alias("lane"))
    assert plan(sub)["lurk"] is False


def recipe_fixture():
    rows=[]
    for site in ("A","B"):
        for i in range(8):
            rows.append(dict(demo_id=f"{site}{i}",round_num=1,gun=True,target=site,
                             exec_spots=["smoke", "m1" if i<4 else "m2"], won=True, team="Red",tempo="fast",
                             plant_site=site, commit_s=30.,exec_flashes=1,split=False))
    plans=pl.DataFrame(rows,schema_overrides={"round_num":pl.Int32})
    spots=pl.DataFrame({"spot_id":["smoke","m1","m2"],"type":["smoke","molotov","molotov"],"label":["s","a","b"],"place":["A"]*3})
    return plans,spots


def test_recipe_smoke_core_merge_unique_ids_disjoint_rounds_and_stable_output():
    plans, spots=recipe_fixture()
    recipes, assignments=execute_recipes(plans, spots, {}, MM)
    assert len(recipes)==2 and len({r["id"] for r in recipes})==2
    assert assignments.height==assignments.unique(["demo_id","round_num"]).height==16
    other, other_ass=execute_recipes(plans.reverse(),spots,{},MM)
    assert recipes==other and assignments.equals(other_ass)


def test_roster_tied_names_counts_and_modes_are_stable():
    pr=pl.DataFrame({"team":["X"]*4,"steamid":[2,1,2,1],"name":["z","z","a","a"]})
    assert roster_order(pr)==roster_order(pr.reverse())=={"X":["1","2"]}


def test_ct_forward_ties_have_stable_steamid_order():
    from playbook.tactics import ct_setups
    sub=_round([(2800.,2000.)])
    sub["team_rounds"]=sub["team_rounds"].with_columns(side=pl.lit("CT"),planted=pl.lit(True))
    sub["positions"]=sub["positions"].with_columns(side=pl.lit("CT"))
    p=t_plans(_round([(2800.,2000.)]),TMM,ASSIGN,{"A":(2000.,2000.,0.)})
    ct=ct_setups(sub,p,{"Ramp"}).with_columns(forward_steamids=pl.lit([103,101,102],dtype=pl.List(pl.UInt64)))
    assert [p["steamid"] for p in ct_summary(ct)["forward_players"]]==["101","102","103"]


def export_tables():
    """Two synthetic matches, both sides, tied names/counts, holds and two utility spots."""
    from playbook.semantics import build_team_rounds, build_player_rounds
    all_sub=[]
    for demo in ("d","e"):
        for rn in range(1,9):
            sub=tables()
            pos=_round([(2800.,2000.),(2000.,2800.)])["positions"]
            pos=pos.with_columns(x=pl.col("x")-2000,y=pl.col("y")-2000)
            ct=pos.with_columns(steamid=pl.col("steamid")+10,side=pl.lit("CT"),team=pl.lit("Blue"))
            sub["positions"]=pl.concat([pos,ct]).with_columns(
                name=pl.lit("alpha" if demo=="d" else "zeta"))
            sub["kills"]=sub["kills"].with_columns(attacker_steamid=pl.lit(100,dtype=pl.UInt64),
                victim_steamid=pl.lit(110,dtype=pl.UInt64),headshot=pl.lit(True),is_trade=pl.lit(False),victim_traded=pl.lit(False))
            u=sub["utility"].with_columns(thrower_steamid=pl.lit(100,dtype=pl.UInt64),
                thrower_name=pl.lit("alpha"),throw_tick=pl.lit(100,dtype=pl.Int64),throw_t_s=pl.lit(25.),pop_t_s=pl.lit(27.),
                land_x=pl.lit(100.),land_y=pl.lit(100.),land_lane=pl.lit("A"),matched=pl.lit(True),
                throw_x=pl.lit(0.),throw_y=pl.lit(0.),throw_z=pl.lit(0.),throw_place=pl.lit("TSpawn"),
                pitch=pl.lit(0.),yaw=pl.lit(0.),is_jumping=pl.lit(False),is_crouched=pl.lit(False),is_walking=pl.lit(False),throw_speed=pl.lit(0.))
            u2=u.with_columns(nade_id=pl.lit(8,dtype=pl.UInt32),type=pl.lit("molotov"),land_x=pl.lit(600.))
            sub["utility"]=pl.concat([u,u2])
            sub["shots"]=sub["shots"].with_columns(steamid=pl.lit(100,dtype=pl.UInt64))
            sub["plants"]=pl.DataFrame({"demo_id":[demo],"round_num":[rn],"tick":[200],"site":["A"],"t_s":[35.],"x":[0.],"y":[0.],"z":[0.]},schema_overrides={"round_num":pl.Int32})
            sub["rounds"]=pl.DataFrame({"demo_id":[demo],"round_num":[rn],"half":[1],"dur_s":[39.],"reason":["bomb_defused"],"winner_team":["Blue"],"ct_team":["Blue"],"t_team":["Red"],"score_ct_before":[rn-1],"score_t_before":[0]},schema_overrides={"round_num":pl.Int32})
            sub["economy"]=sub["team_rounds"].select("demo_id","round_num","team","side","buy_type").with_columns(equipment_value=pl.lit(20000))
            sub["loadouts"]=sub["positions"].filter(pl.col("t_s")==0).select("demo_id","round_num","steamid","name","team","side").with_columns(primary_weapon=pl.lit("ak47"))
            sub={k:v.with_columns(demo_id=pl.lit(demo),round_num=pl.lit(rn,dtype=pl.Int32)) for k,v in sub.items() if k not in ("team_rounds","player_rounds")}
            sub["team_rounds"]=build_team_rounds(sub)
            sub["player_rounds"]=build_player_rounds(sub,sub["team_rounds"])
            all_sub.append(sub)
    out={k:pl.concat([s[k] for s in all_sub]) for k in all_sub[0]}
    out["matches"]=pl.DataFrame({"demo_id":["d","e"],"map":["de_mirage"]*2,"team_a":["Red"]*2,"team_b":["Blue"]*2,"score_a":[0]*2,"score_b":[4]*2,"hltv_match_id":[1,2]})
    return out


def test_export_twice_in_fresh_processes_is_byte_identical_except_timestamp(tmp_path):
    from playbook.store import write_tables
    parsed=tmp_path/"parsed"
    fixture = export_tables()
    fixture["team_rounds"] = fixture["team_rounds"].with_columns(plant_t_s=pl.lit(99.), plant_site=pl.lit("B"))
    write_tables(fixture,"fixture",parsed)
    outputs=[]
    for i in range(2):
        target=tmp_path/f"site{i}"
        subprocess.run([sys.executable,"-m","playbook","export","--parsed",str(parsed),"--out",str(target)],check=True,capture_output=True,text=True,
                       env={**os.environ,"PYTHONHASHSEED":str(i)})
        files={str(p.relative_to(target)):p.read_text() for p in target.rglob("*.json")}
        idx=json.loads(files["index.json"]);idx.pop("generated_at")
        files["index.json"]=json.dumps(idx)
        outputs.append(files)
    assert len(outputs[0])>=10
    assert outputs[0]==outputs[1]
    red = json.loads(outputs[0]["de_mirage/teams/red.json"])
    assert red["sides"]["T"]["avg_plant_t_s"] == 35.
    assert red["sides"]["T"]["plant_sites"][0]["value"] == "A"


def test_typescript_python_layers_colours_owner_and_blur_parity(tmp_path):
    node=shutil.which("node")
    if not node:
        pytest.skip("Node with native TypeScript support is not installed")
    import importlib.util
    spec = importlib.util.spec_from_file_location("heatmap_preview", Path(__file__).resolve().parents[1]/"scripts/heatmap_preview.py")
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    player_rgba, owner_rgba, blur_grid = preview.player_rgba, preview.owner_rgba, preview.blur_grid
    pytest.importorskip("scipy.ndimage")
    root=Path(__file__).resolve().parents[1]
    entry={"data":{"T":{"early":{"presence":[0,1.,4096,.4]},"post":{"presence":[4096,.6,8191,.1]}}}}
    dense=to_array(merge_phases(entry,"T")["presence"],2)
    # Different player peaks expose incorrect global normalization of owner colours.
    players=np.zeros((2,2,64,64));players[0]=dense
    players[1,0,0,0]=.2;players[1,0,0,1]=.1
    players[1,1,0,0]=.3;players[1,1,0,1]=.1
    payload={"entry":entry,"players":[p.ravel().tolist() for p in players]}
    script=f'''import fs from 'node:fs';
import {{denseLayers,playerRgba,ownerRgba,playerColor,blur}} from {json.dumps((root/'web/src/heatmap.ts').as_uri())};
const input=JSON.parse(fs.readFileSync(0,'utf8')), shape={{grid:64,levels:2}};
const ps=input.players.map((v,i)=>({{values:new Float32Array(v),color:playerColor(i)}}));
console.log(JSON.stringify({{
 dense:Array.from(denseLayers(input.entry,'T',['early','mid','post'],shape).presence),
 player:[0,1].map(l=>[0,1,2,3,4,5].map(c=>Array.from(playerRgba(ps[0].values,shape,l,playerColor(c))))),
 owner:[0,1].map(l=>Array.from(ownerRgba(ps,shape,l))),
 blur:Array.from(blur(ps[0].values,shape,1))
}}));'''
    result=subprocess.run([node,"--input-type=module","-e",script],input=json.dumps(payload),text=True,capture_output=True,check=True)
    got=json.loads(result.stdout)
    np.testing.assert_allclose(got["dense"],dense.ravel(),atol=1e-7)
    for level in (0,1):
        for color in range(6):
            py=player_rgba(dense[level],color)*255
            ts=np.array(got["player"][level][color]).reshape(64,64,4)
            assert np.max(np.abs(ts-py))<=1
        py=owner_rgba(players[:,level], [0,1])*255
        ts=np.array(got["owner"][level]).reshape(64,64,4)
        assert np.max(np.abs(ts-py))<=1
    expected=np.array([blur_grid(d,1) for d in dense])
    np.testing.assert_allclose(got["blur"],expected.ravel(),atol=1e-7)


def test_player_tactic_rates_use_own_rounds_across_teams_and_substitutions(tmp_path):
    from playbook.export import _add_player_tactics
    plans=pl.DataFrame({"demo_id":["d","e"],"round_num":[1,1],"team":["Red","Green"],
                        "gun":[True,True],"commit_s":[30.,30.],"lurk":[True,True],"lurker_steamid":[100,100]})
    ct=pl.DataFrame({"gun":[True,True],"team":["Red","Green"],"forward_steamids":[[100],[100]]})
    pr=pl.DataFrame({"demo_id":["d","e","d","e"],"round_num":[1,1,2,2],"team":["Red","Green","Red","Green"],
                    "side":["T","T","CT","CT"],"steamid":[100]*4,"buy_type":["full"]*4})
    players=[{"steamid":"100","team":"Red","T":{},"CT":{}}]
    _add_player_tactics(tmp_path,players,{"plans":plans,"ct":ct},pr)
    assert players[0]["T"]["lurk_share"]==1.0
    assert players[0]["CT"]["forward_share"]==1.0


def test_plant_tick_bounds_avoid_rounded_duration_and_time_ties():
    sub = tables()
    sub["rounds"]=pl.DataFrame({"demo_id":["d"],"round_num":[1],"freeze_end_tick":[100],"end_tick":[102],"dur_s":[0.]},schema_overrides={"round_num":pl.Int32})
    sub["plants"]=pl.DataFrame({"demo_id":["d"]*3,"round_num":[1]*3,"tick":[101,102,103],"t_s":[.01,.01,.02],"site":["B","A","A"]},schema_overrides={"round_num":pl.Int32})
    assert round_plants(sub).select("plant_site","plant_t_s").rows()==[("B",.01)]
    sub["plants"]=sub["plants"].filter(pl.col("tick")>102)
    assert round_plants(sub).is_empty()


def test_holding_clusters_with_unknown_callout_do_not_crash_on_tied_counts():
    p=clean_frames(tables(),MM)["presence"].filter(pl.col("holding"))
    unknown=p.with_columns(x=pl.col("x")+500,radar_x=pl.col("radar_x")+500,place=pl.lit(None,dtype=pl.String))
    assert len(_holds(pl.concat([p,p,unknown,unknown]),1))==2
