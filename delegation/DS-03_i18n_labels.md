# DS-03：网站中英文文案与点位译名（交给 DeepSeek）

> 用法：从分割线开始整段粘贴给 DeepSeek，把返回的两个 JSON 原样贴回给 Claude。

---

你是熟悉 CS2（国服和国际社区）的中英文本地化编辑。我在做一个开源网站，把职业比赛数据整理成普通玩家能看懂的战术、选手打法和道具教学。需要你提供网站的中文和英文文案。

## 要求

- 中文使用国内 CS 玩家最常用的说法。例如烟雾弹、闪光弹、燃烧瓶、手雷；跳投、跑投；手枪局、ECO、强起、长枪局；狙击手、自由人、突破手。中文用户群里同一个东西有多种叫法时，选最通用的一种。
- 英文使用国际社区通行叫法，例如 Window、Top Mid、Banana、Pit。
- 点位（callout）按地图分开翻译，因为同名点位在不同地图上不是同一个地方：Mirage 的 `Apartments` 是 B 区的公寓；Inferno 的 `Apartments` 是 A 区一侧的二楼。
- 文案简短。`role_desc` 和 `metric_desc` 每条一句话，写给普通玩家看，不用术语堆砌。

## 输出格式（严格遵守）

输出两个代码块：先 ```json（zh.json），再 ```json（en.json）。两份的键结构必须完全相同，只有值不同。键名一个都不能改，也不能增删。带 `{n}` 的占位符要原样保留。

```json
{
  "ui": {
    "app_title": "", "nav_maps": "", "nav_lineups": "", "nav_teams": "", "nav_players": "",
    "low_sample_warning": "（必须包含 {n}，表示比赛场数）",
    "copy_cmd": "", "copied": "", "practice_hint": "（说明：在练习服控制台粘贴，需要 sv_cheats 1）",
    "filter_side": "", "filter_type": "", "filter_lane": "", "filter_min_throws": "", "filter_technique": "", "filter_all": "",
    "setups_title": "", "setup_shape_help": "（解释 A2 M2 B1 这种写法：A 区 2 人、中路 2 人、B 区 1 人；S = T 家，C = CT 家）",
    "plant_sites_title": "", "execute_title": "", "economy_title": "", "matches_title": "",
    "retake_title": "", "roles_title": "", "throwers": "", "times_thrown": "", "round_win_rate": "",
    "language": "", "generated_at": "", "data_source_note": ""
  },
  "side": { "T": "", "CT": "" },
  "lane": { "T_SPAWN": "", "A": "", "MID": "", "B": "", "CT_SPAWN": "", "OTHER": "" },
  "region": { "T_SPAWN": "", "A_APPROACH": "", "A_SITE": "", "MID": "", "B_APPROACH": "", "B_SITE": "", "CT_SPAWN": "", "OTHER": "" },
  "grenade": { "smoke": "", "flashbang": "", "molotov": "", "he": "" },
  "technique": { "jump": "", "run": "", "crouch": "", "walk": "", "stand": "" },
  "buy": { "pistol": "", "eco": "", "force": "", "full": "" },
  "execute_timing": { "fast": "", "default_then_execute": "", "late": "", "no_clear_execute": "" },
  "role": { "awper": "", "a_anchor": "", "b_anchor": "", "mid_ct": "", "lurker": "", "entry": "", "support": "" },
  "role_desc": { "awper": "", "a_anchor": "", "b_anchor": "", "mid_ct": "", "lurker": "", "entry": "", "support": "" },
  "metric": {
    "kpr": "", "dpr": "", "hs_pct": "", "opening_kills_pr": "", "opening_deaths_pr": "", "opening_success": "",
    "traded_death_rate": "", "awp_share": "", "util_pr": "", "avg_dist_to_team_30s": "", "first_into_site_rate": "",
    "win_rate": "", "opening_win_rate": "", "avg_first_kill_s": "", "avg_util_per_round": "", "avg_early_util": "",
    "retake_win_rate": "", "stack_rate_15s": "", "round_win_rate": "", "n_throws": "", "median_pop_t_s": "",
    "ct_lane_15s_share": "", "t_avg_dist_to_team_30s": "", "t_first_into_site_rate": ""
  },
  "metric_desc": { "（与 metric 完全相同的键，每条一句话解释该指标的含义）": "" },
  "callout": {
    "de_mirage": {
      "TSpawn": "", "PalaceAlley": "", "PalaceInterior": "", "Scaffolding": "", "TRamp": "", "BombsiteA": "",
      "Stairs": "", "Jungle": "", "Connector": "", "TopofMid": "", "Middle": "", "Catwalk": "", "Ladder": "",
      "SnipersNest": "", "Underpass": "", "SideAlley": "", "House": "", "BackAlley": "", "Apartments": "",
      "BombsiteB": "", "Shop": "", "Truck": "", "CTSpawn": ""
    },
    "de_inferno": {
      "TSpawn": "", "LowerMid": "", "Upstairs": "", "Bridge": "", "Kitchen": "", "TRamp": "", "Deck": "",
      "Underpass": "", "Banana": "", "BombsiteB": "", "SecondMid": "", "Middle": "", "BackAlley": "", "Ruins": "",
      "Apartments": "", "TopofMid": "", "Quad": "", "Arch": "", "BombsiteA": "", "Balcony": "", "CTSpawn": "",
      "Pit": "", "Library": ""
    }
  }
}
```

说明：

- `metric_desc` 的键与 `metric` 完全相同（共 24 个），上面那一行只是占位说明。
- 指标含义参考：`kpr` = 每回合击杀；`dpr` = 每回合死亡；`opening_success` = 首杀对枪胜率；`traded_death_rate` = 阵亡后被队友补枪的比例；`util_pr` = 每回合投掷道具数；`avg_dist_to_team_30s` = 回合开始 30 秒时与队友的平均距离（越大越像自由人）；`first_into_site_rate` = 进点时第一个进包点的比例；`avg_early_util` = 开局 15 秒内的控图道具数；`stack_rate_15s` = CT 开局 15 秒有 3 人以上堆在同一包点的比例；`median_pop_t_s` = 道具通常在回合第几秒生效；`ct_lane_15s_share`、`t_avg_dist_to_team_30s`、`t_first_into_site_rate` 是角色判定依据的名字，含义分别同 CT 开局站位占比、T 方与队友距离、T 方首个进点比例。

## 自检清单

- [ ] 两份 JSON 都能被 `JSON.parse` 解析，没有尾随逗号和注释
- [ ] 两份键结构完全一致；`metric_desc` 恰好 24 个键，与 `metric` 一一对应
- [ ] Mirage 23 个点位、Inferno 23 个点位全部有值
- [ ] `low_sample_warning` 中保留了 `{n}`
- [ ] 中文用的是玩家常用叫法，没有生硬直译
