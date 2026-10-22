"""Round-two teaching metadata must use the selected recipe and actual team sides."""
import polars as pl
import pytest

from playbook.export import build_lineups, map_card_summary, team_round_sides
from playbook.tactics import execute_recipes
from test_export_lineups import synthetic_tables
from test_review02 import recipe_fixture
from test_tactics import MM


def test_recipe_thrower_and_order_are_local_to_recipe_execute_window():
    plans, spots = recipe_fixture()
    rows = []
    for plan in plans.iter_rows(named=True):
        for spot in plan['exec_spots']:
            rows.append(dict(demo_id=plan['demo_id'], round_num=1, spot_id=spot,
                             thrower_name='Alice' if plan['demo_id'].endswith(('0', '1', '2')) else 'Bob',
                             thrower_team='Red', thrower_side='T', is_post_round=False,
                             land_lane=plan['target'], pop_t_s=35. if spot == 'smoke' else 25.))
    # Many irrelevant throws cannot win the mode or change the median.
    for _ in range(30):
        for changes in [dict(pop_t_s=100.), dict(thrower_side='CT'), dict(is_post_round=True),
                        dict(thrower_team='Blue'), dict(demo_id='unrelated')]:
            rows.append({**rows[0], 'thrower_name': 'Wrong', **changes})
    utility = pl.DataFrame(rows, schema_overrides={'round_num': pl.Int32})
    recipes, _ = execute_recipes(plans, spots, {}, MM, utility)
    assert len(recipes) == 2
    for recipe in recipes:
        refs = {s['spot_id']: s for s in recipe['core'] + recipe['options']}
        assert refs['smoke']['thrower'] == 'Bob'
        assert refs['m1']['thrower'] == 'Alice'
        assert refs['m2']['thrower'] == 'Bob'
        assert refs['smoke']['order'] == 3
        assert {refs['m1']['order'], refs['m2']['order']} == {1, 2}
    reversed_recipes, _ = execute_recipes(plans.reverse(), spots, {}, MM, utility.reverse())
    assert recipes == reversed_recipes


def test_existing_yaw_and_technique_are_exported_from_representative_throw():
    sub = synthetic_tables()
    sub['utility'] = sub['utility'].with_columns(yaw=pl.lit(123.45), is_jumping=pl.lit(True))
    lineups, _ = build_lineups(sub, MM)
    assert lineups
    for lineup in lineups:
        assert lineup['throw']['yaw'] == pytest.approx(123.45)
        assert lineup['technique'] == 'jump'
        assert '123.45' in lineup['practice_cmd']


def test_round_sides_include_halftime_and_overtime_without_guessing():
    rows = pl.DataFrame({'demo_id': ['d'] * 4 + ['other'], 'team': ['Red'] * 5,
                         'round_num': [1, 13, 25, 28, 1], 'side': ['CT', 'T', 'T', 'CT', 'T']})
    assert team_round_sides(rows, 'd') == {'red': {'1': 'CT', '13': 'T', '25': 'T', '28': 'CT'}}


def test_home_summary_uses_round_results_and_most_used_recipe():
    rounds = pl.DataFrame({'side': ['T'] * 3 + ['CT'] * 3, 'won': [True, True, False, False, False, True]})
    recipes = [{'id': 'less', 'n_rounds': 2, 'core': []},
               {'id': 'top', 'n_rounds': 8, 'core': [{'label': 'A', 'name': {'zh': '烟', 'en': 'Smoke'}}]}]
    summary = map_card_summary(rounds, recipes)
    assert summary['win_rate_T'] == .667 and summary['win_rate_CT'] == .333
    assert summary['top_recipe'] == {'id': 'top', 'name': {'zh': '烟', 'en': 'Smoke'}}
    empty = map_card_summary(rounds.head(0), [])
    assert empty == {'win_rate_T': None, 'win_rate_CT': None, 'top_recipe': None}
