# DS-05：其余地图的点位映射 + 中英文译名（交给 DeepSeek）

> 本文件由 `scripts/make_map_briefs.py --brief` 生成，表格来自真实职业比赛 demo。不要手改表格；要更新时重新运行脚本。
>
> 用法：把本文件**从下面的分割线开始整段**发给 DeepSeek（DSH 工作区能直接读写仓库文件）。它改完文件后，把回复里的"交付报告"一节原样贴给 Claude 审核。

---

你是熟悉 CS2 职业比赛和地图点位的数据工程师。我们在做开源项目 cs2-pro-playbook：从职业比赛 demo 中自动分析战术。这一轮请你为这些地图完成两件事：`de_ancient`, `de_anubis`, `de_dust2`, `de_nuke`, `de_overpass`

1. **点位 → 区域 → 路线映射**：写进每张图的 `config/maps/<map>.toml`。
2. **点位的中英文译名**：写进网站文案 `web/src/i18n/zh.json` 和 `web/src/i18n/en.json`。

## 0. 工作目录和文件位置

- 仓库根目录：`/Users/stephen/Downloads/cs2-pro-playbook`。下文所有路径都相对这个目录。
- **只允许修改**下面这些文件，其他文件一律不要动：

| 用途 | 文件 | 改哪里 |
|---|---|---|
| 点位映射 | `config/maps/<map>.toml`（每张图一个，文件已存在） | 只填 `[regions]` 和 `[callouts]`；文件头注释、`map`、`display_name`、`[radar]`（含 `lower_level_max_z`）保持原样 |
| 中文译名 | `web/src/i18n/zh.json` | 在顶层 `"callout"` 对象里，为每张图新增一个键，例如 `"de_nuke": { ... }`，与已有的 `"de_mirage"`、`"de_inferno"` 并列 |
| 英文译名 | `web/src/i18n/en.json` | 同上，键结构和 zh.json 完全一致 |

- **只读参考**（不要修改）：
  - `config/maps/de_mirage.toml`、`config/maps/de_inferno.toml`：已审核通过的映射样例
  - `web/src/i18n/zh.json` 里的 `callout.de_mirage`、`callout.de_inferno`：已确认的中文译名风格。例如 Mirage 的 `SnipersNest` 叫"VIP 狙位"，`Catwalk` 叫"中路短"
  - `delegation/inputs/<map>_callouts.csv`：每张图的点位输入表，与文末的表格相同
  - `web/public/radars/<map>.png`：雷达图。表里的 `radar_x`/`radar_y` 是这张 1024×1024 图上的像素坐标，可以打开图片对照位置
- 自检脚本：`scripts/check_map_config.py`，只用标准库，需要 Python 3.11 以上。

## 1. 点位映射的规则

每张图的配置文件格式与 `config/maps/de_mirage.toml` 相同：

```toml
[regions]          # 区域 → 路线
T_SPAWN = "T_SPAWN"
A_APPROACH = "A"   # T 方进攻 A 的通道
A_SITE = "A"       # A 包点，以及 CT 防守 A 的站位
MID = "MID"
B_APPROACH = "B"
B_SITE = "B"
CT_SPAWN = "CT_SPAWN"

[callouts]         # 游戏内点位名 → 区域
TSpawn = "T_SPAWN"
BombsiteA = "A_SITE"
...
```

- 路线（lane）**只能**取 5 个值：`T_SPAWN`、`A`、`MID`、`B`、`CT_SPAWN`。这是硬约束，网站和分析代码都依赖它。
- 区域（region）建议沿用上面 7 个。如果某张图确实需要别的划分，可以新增区域，但每个新区域都必须指向上面 5 个路线之一，并在该行行尾用注释说明理由。例如 Nuke 的 B 点在 A 点正下方，可以加 `LOWER = "B"  # 下层通往 B 点的区域`。
- `[callouts]` 必须**恰好**包含输入表里的全部点位，名字的拼写和大小写与表格完全一致；不能漏，也不能多写表里没有的点位。
- `TSpawn` → T_SPAWN，`CTSpawn` → CT_SPAWN，`BombsiteA` → A 路线，`BombsiteB` → B 路线。

**怎么判断一个点位属于 A 还是 B**：不要只凭记忆，看表格里的三列数据：

- `t_when_a_plant` 比 `t_when_b_plant` 明显大：T 方下 A 的回合常经过这里，归 A 侧。反之归 B 侧。
- 两列差不多大，且 `samples` 多：通常是中路或公共区域，归 `MID`。
- `ct_first_20s` 大：这是 CT 开局站位，通常归 `A_SITE` 或 `B_SITE`，看它离哪个包点近。
- 再结合 `x, y, z` 坐标和雷达图核对。同名点位在不同地图上不是同一个地方。
- 拿不准的点位，在行尾加 `# ?` 注释并写一句理由。

## 2. 译名的规则

- 中文用国内 CS 玩家最常用的叫法；英文用国际社区通行叫法。
- 每张图在两份文件里各写一个对象，键是输入表里的全部点位名，值是译名，不能为空：

```json
"callout": {
  "de_mirage": { "...": "..." },
  "de_inferno": { "...": "..." },
  "de_nuke": { "TSpawn": "T 家", "BombsiteA": "A 包点", "...": "..." }
}
```

- 两份 JSON 必须仍然能被 `JSON.parse` 解析：不要留尾随逗号，也不要写注释。不要改动其他键。

## 3. 自检（必须全部通过才算完成）

在仓库根目录运行：

```bash
python3 scripts/check_map_config.py de_ancient de_anubis de_dust2 de_nuke de_overpass
```

每张图都要输出 `OK`。出现 `FAIL` 就按提示修改后重新运行，直到全部通过。

## 4. 交付报告（回复格式）

只需回复下面三部分，**不要**贴文件全文：

1. 自检命令的完整输出。
2. 每张图拿不准的点位：最多 5 行，写明点位名、你的归类和理由，要引用表格里的数据。
3. 你新增的区域（如果有）及理由。

## 各地图输入

### Ancient（`de_ancient`）

- 来源 demo：FUT Esports vs MOUZ (13-11, mouz-vs-fut-m1-ancient.dem)
- 输入表：`delegation/inputs/de_ancient_callouts.csv`（共 18 个点位，下表与之相同）
- 要改的文件：`config/maps/de_ancient.toml`；`web/src/i18n/zh.json` 和 `web/src/i18n/en.json` 里的 `callout.de_ancient`
- 雷达图（核对位置用）：`web/public/radars/de_ancient.png`，表中 radar_x / radar_y 是这张 1024×1024 图上的像素坐标

| callout | samples | x | y | z | radar_x | radar_y | t_when_a_plant | t_when_b_plant | ct_first_20s |
|---|---|---|---|---|---|---|---|---|---|
| MainHall | 1258 | -1938 | -73 | 76 | 203 | 447 | 501 | 222 | 21 |
| BombsiteA | 2006 | -1576 | 728 | 68 | 275 | 287 | 769 | 6 | 242 |
| SideHall | 1288 | -1412 | -18 | 104 | 308 | 436 | 472 | 0 | 133 |
| Outside | 1510 | -1230 | -1070 | -6 | 345 | 647 | 698 | 397 | 0 |
| Middle | 1140 | -678 | -560 | 58 | 455 | 545 | 210 | 138 | 239 |
| TSpawn | 727 | -584 | -2017 | -163 | 474 | 836 | 254 | 232 | 0 |
| TopofMid | 76 | -536 | 154 | 163 | 483 | 402 | 2 | 0 | 43 |
| CTSpawn | 1211 | -448 | 1239 | 64 | 501 | 185 | 54 | 7 | 562 |
| House | 815 | -445 | 758 | 105 | 502 | 281 | 7 | 3 | 399 |
| Tunnel | 254 | 143 | -1836 | -160 | 619 | 800 | 59 | 124 | 0 |
| TSideUpper | 597 | 227 | -797 | 153 | 636 | 592 | 151 | 250 | 27 |
| SideEntrance | 1805 | 445 | -183 | 170 | 680 | 469 | 66 | 406 | 189 |
| Water | 276 | 544 | -1867 | -157 | 699 | 806 | 28 | 191 | 0 |
| Alley | 1540 | 612 | 799 | 113 | 713 | 273 | 1 | 69 | 418 |
| Ruins | 758 | 1023 | -1256 | 4 | 795 | 684 | 125 | 499 | 0 |
| BombsiteB | 1614 | 1044 | 219 | 131 | 799 | 389 | 2 | 382 | 200 |
| TSideLower | 1090 | 1058 | -735 | 20 | 802 | 580 | 233 | 670 | 0 |
| Ramp | 515 | 1237 | -483 | 46 | 838 | 529 | 24 | 298 | 9 |

### Anubis（`de_anubis`）

- 来源 demo：FURIA vs Falcons (8-13, furia-vs-falcons-m2-anubis.dem)
- 输入表：`delegation/inputs/de_anubis_callouts.csv`（共 28 个点位，下表与之相同）
- 要改的文件：`config/maps/de_anubis.toml`；`web/src/i18n/zh.json` 和 `web/src/i18n/en.json` 里的 `callout.de_anubis`
- 雷达图（核对位置用）：`web/public/radars/de_anubis.png`，表中 radar_x / radar_y 是这张 1024×1024 图上的像素坐标

| callout | samples | x | y | z | radar_x | radar_y | t_when_a_plant | t_when_b_plant | ct_first_20s |
|---|---|---|---|---|---|---|---|---|---|
| OutsideLong | 1101 | -1356 | -32 | 1 | 276 | 644 | 146 | 656 | 11 |
| Alley | 376 | -1179 | 1236 | 0 | 310 | 401 | 15 | 0 | 152 |
| SnipersNest | 157 | -1144 | 1797 | 48 | 316 | 293 | 6 | 0 | 35 |
| BombsiteB | 2349 | -1041 | 591 | -0 | 336 | 524 | 24 | 450 | 454 |
| Ruins | 1087 | -946 | -641 | 70 | 354 | 760 | 115 | 615 | 0 |
| LowerTunnel | 142 | -902 | 1575 | -31 | 363 | 336 | 0 | 0 | 75 |
| Bricks | 63 | -888 | 1089 | 35 | 366 | 429 | 1 | 8 | 4 |
| Connector | 516 | -740 | 238 | -72 | 394 | 592 | 15 | 122 | 85 |
| BackofB | 394 | -734 | 662 | 38 | 395 | 511 | 0 | 171 | 56 |
| CTSideUpper | 358 | -476 | 2066 | 22 | 444 | 242 | 3 | 0 | 263 |
| Bridge | 718 | -353 | -232 | 0 | 468 | 682 | 273 | 197 | 3 |
| Water | 8 | -286 | 2942 | -161 | 481 | 74 | 7 | 0 | 0 |
| PalaceInterior | 744 | -245 | 1417 | 32 | 489 | 366 | 2 | 39 | 155 |
| TSpawn | 651 | -101 | -1429 | 2 | 516 | 911 | 237 | 229 | 0 |
| CTSpawn | 114 | 60 | 2521 | -120 | 547 | 155 | 10 | 0 | 0 |
| MidDoors | 201 | 180 | 478 | -29 | 570 | 546 | 60 | 0 | 55 |
| Middle | 1309 | 233 | 1239 | -30 | 580 | 400 | 78 | 0 | 462 |
| Tunnel | 121 | 353 | 2242 | -150 | 603 | 208 | 16 | 0 | 0 |
| TunnelStairs | 61 | 531 | 1893 | -39 | 637 | 275 | 9 | 0 | 0 |
| Street | 577 | 769 | -580 | -12 | 683 | 749 | 261 | 182 | 0 |
| Canal | 2054 | 769 | 306 | -149 | 683 | 579 | 838 | 537 | 36 |
| TStairs | 484 | 773 | -84 | -94 | 684 | 654 | 150 | 185 | 0 |
| Walkway | 611 | 820 | 1401 | -88 | 693 | 369 | 171 | 0 | 67 |
| Heaven | 331 | 874 | 2141 | -40 | 703 | 227 | 100 | 0 | 0 |
| BombsiteA | 777 | 1269 | 1673 | -152 | 779 | 317 | 270 | 0 | 106 |
| TSideUpper | 348 | 1356 | 459 | 0 | 795 | 550 | 185 | 51 | 0 |
| Main | 947 | 1597 | 1163 | -152 | 842 | 415 | 326 | 43 | 108 |
| Fountain | 470 | 1726 | 1792 | -78 | 866 | 294 | 83 | 10 | 69 |

### Dust II（`de_dust2`）

- 来源 demo：Falcons vs Spirit (16-12, spirit-vs-falcons-m3-dust2.dem)
- 输入表：`delegation/inputs/de_dust2_callouts.csv`（共 24 个点位，下表与之相同）
- 要改的文件：`config/maps/de_dust2.toml`；`web/src/i18n/zh.json` 和 `web/src/i18n/en.json` 里的 `callout.de_dust2`
- 雷达图（核对位置用）：`web/public/radars/de_dust2.png`，表中 radar_x / radar_y 是这张 1024×1024 图上的像素坐标

| callout | samples | x | y | z | radar_x | radar_y | t_when_a_plant | t_when_b_plant | ct_first_20s |
|---|---|---|---|---|---|---|---|---|---|
| TRamp | 21 | -1816 | -465 | 97 | 150 | 842 | 0 | 0 | 0 |
| BombsiteB | 3009 | -1773 | 2268 | 5 | 160 | 221 | 0 | 660 | 406 |
| UpperTunnel | 1710 | -1706 | 1155 | 35 | 175 | 474 | 168 | 695 | 6 |
| OutsideTunnel | 333 | -1592 | 374 | 25 | 201 | 651 | 67 | 121 | 0 |
| Hole | 136 | -1311 | 2671 | 125 | 265 | 129 | 0 | 16 | 15 |
| BDoors | 860 | -1127 | 2256 | 2 | 307 | 223 | 0 | 42 | 103 |
| TunnelStairs | 218 | -1118 | 1147 | -42 | 309 | 475 | 54 | 82 | 0 |
| LowerTunnel | 520 | -794 | 1382 | -111 | 382 | 422 | 109 | 130 | 63 |
| TSpawn | 1137 | -499 | -740 | 115 | 449 | 904 | 232 | 270 | 0 |
| MidDoors | 1584 | -464 | 2026 | -119 | 457 | 276 | 58 | 190 | 467 |
| Middle | 523 | -309 | 1345 | -105 | 492 | 430 | 113 | 108 | 12 |
| TopofMid | 977 | -266 | 346 | 1 | 502 | 658 | 337 | 157 | 3 |
| Catwalk | 924 | -113 | 1377 | 1 | 537 | 423 | 213 | 51 | 47 |
| CTSpawn | 1166 | 182 | 2207 | -124 | 604 | 235 | 10 | 19 | 460 |
| OutsideLong | 1272 | 285 | 9 | 1 | 628 | 734 | 347 | 122 | 0 |
| ShortStairs | 779 | 379 | 1637 | 39 | 649 | 364 | 245 | 3 | 118 |
| ExtendedA | 670 | 466 | 2186 | 98 | 669 | 239 | 157 | 5 | 64 |
| LongDoors | 1620 | 713 | 795 | 1 | 725 | 555 | 311 | 21 | 59 |
| UnderA | 1040 | 773 | 2224 | 1 | 738 | 231 | 1 | 13 | 344 |
| BombsiteA | 445 | 1101 | 2590 | 97 | 813 | 148 | 168 | 0 | 8 |
| ARamp | 946 | 1356 | 2475 | 60 | 871 | 174 | 138 | 0 | 47 |
| Pit | 214 | 1386 | 560 | -75 | 878 | 609 | 13 | 0 | 13 |
| LongA | 2218 | 1419 | 1543 | 1 | 885 | 385 | 174 | 11 | 703 |
| Side | 41 | 1665 | 984 | 1 | 941 | 512 | 25 | 0 | 0 |

### Nuke（`de_nuke`）

- 来源 demo：Aurora vs FURIA (4-13, aurora-vs-furia-m2-nuke.dem)
- 输入表：`delegation/inputs/de_nuke_callouts.csv`（共 28 个点位，下表与之相同）
- 要改的文件：`config/maps/de_nuke.toml`；`web/src/i18n/zh.json` 和 `web/src/i18n/en.json` 里的 `callout.de_nuke`
- 雷达图（核对位置用）：`web/public/radars/de_nuke.png`，表中 radar_x / radar_y 是这张 1024×1024 图上的像素坐标

| callout | samples | x | y | z | radar_x | radar_y | t_when_a_plant | t_when_b_plant | ct_first_20s |
|---|---|---|---|---|---|---|---|---|---|
| TSpawn | 630 | -1312 | -1099 | -416 | 306 | 569 | 176 | 85 | 0 |
| Vending | 301 | -127 | -489 | -416 | 475 | 482 | 38 | 92 | 7 |
| Lobby | 983 | -79 | -969 | -416 | 482 | 551 | 380 | 70 | 2 |
| Roof | 278 | -7 | -885 | -145 | 492 | 539 | 72 | 20 | 0 |
| Trophy | 127 | 56 | -360 | -416 | 501 | 464 | 19 | 20 | 4 |
| Squeaky | 281 | 91 | -1232 | -416 | 506 | 588 | 102 | 32 | 0 |
| Control | 240 | 156 | -43 | -416 | 516 | 419 | 5 | 53 | 8 |
| Silo | 109 | 219 | -1478 | -44 | 525 | 624 | 0 | 0 | 0 |
| Decon | 29 | 232 | -1392 | -776 | 526 | 611 | 0 | 6 | 0 |
| HutRoof | 189 | 353 | -1020 | -256 | 544 | 558 | 0 | 0 | 50 |
| Hut | 234 | 390 | -976 | -392 | 549 | 552 | 115 | 0 | 4 |
| Outside | 2376 | 507 | -1567 | -416 | 566 | 636 | 383 | 234 | 509 |
| Ramp | 1343 | 580 | 202 | -416 | 576 | 384 | 13 | 86 | 235 |
| Vents | 148 | 636 | -1437 | -608 | 584 | 618 | 35 | 32 | 5 |
| Rafters | 309 | 671 | -584 | -128 | 589 | 496 | 4 | 0 | 153 |
| Mini | 145 | 749 | -1599 | -416 | 600 | 641 | 9 | 1 | 24 |
| BombsiteA | 1549 | 766 | -1037 | -416 | 603 | 561 | 415 | 1 | 129 |
| BombsiteB | 566 | 773 | -726 | -640 | 604 | 516 | 0 | 178 | 15 |
| Admin | 169 | 1091 | -52 | -416 | 649 | 420 | 6 | 0 | 56 |
| Heaven | 301 | 1108 | -394 | -128 | 652 | 469 | 8 | 0 | 107 |
| Tunnels | 730 | 1168 | -1524 | -640 | 660 | 630 | 52 | 196 | 19 |
| LockerRoom | 68 | 1194 | -643 | -416 | 664 | 504 | 0 | 0 | 9 |
| Hell | 263 | 1222 | -436 | -416 | 668 | 475 | 7 | 0 | 101 |
| Observation | 65 | 1267 | -639 | -640 | 674 | 504 | 0 | 26 | 5 |
| Catwalk | 99 | 1321 | -396 | -128 | 682 | 469 | 0 | 0 | 18 |
| Secret | 383 | 1509 | -2370 | -560 | 709 | 751 | 9 | 103 | 9 |
| Garage | 292 | 1782 | -1976 | -416 | 748 | 695 | 0 | 0 | 42 |
| CTSpawn | 316 | 2378 | -470 | -352 | 833 | 480 | 0 | 0 | 255 |

### Overpass（`de_overpass`）

- 来源 demo：G2 vs Spirit (13-9, g2-vs-spirit-m1-overpass.dem)
- 输入表：`delegation/inputs/de_overpass_callouts.csv`（共 25 个点位，下表与之相同）
- 要改的文件：`config/maps/de_overpass.toml`；`web/src/i18n/zh.json` 和 `web/src/i18n/en.json` 里的 `callout.de_overpass`
- 雷达图（核对位置用）：`web/public/radars/de_overpass.png`，表中 radar_x / radar_y 是这张 1024×1024 图上的像素坐标

| callout | samples | x | y | z | radar_x | radar_y | t_when_a_plant | t_when_b_plant | ct_first_20s |
|---|---|---|---|---|---|---|---|---|---|
| UpperPark | 1233 | -3483 | -487 | 518 | 259 | 436 | 51 | 16 | 124 |
| Restroom | 142 | -2893 | -908 | 446 | 373 | 517 | 0 | 0 | 30 |
| BombsiteA | 1672 | -2537 | 709 | 484 | 441 | 206 | 95 | 0 | 307 |
| Playground | 246 | -2531 | -2675 | 478 | 442 | 857 | 22 | 73 | 0 |
| Lobby | 196 | -2520 | 1231 | 484 | 444 | 106 | 13 | 0 | 0 |
| StorageRoom | 127 | -2425 | 1292 | 360 | 463 | 94 | 11 | 0 | 1 |
| Fountain | 1144 | -2387 | -2173 | 477 | 470 | 760 | 286 | 192 | 1 |
| LowerPark | 2716 | -2385 | -545 | 436 | 470 | 447 | 389 | 48 | 517 |
| BackofA | 392 | -1971 | 1084 | 460 | 550 | 134 | 10 | 0 | 99 |
| UnderA | 510 | -1945 | 512 | 132 | 555 | 244 | 0 | 0 | 176 |
| SnipersNest | 407 | -1937 | 561 | 260 | 557 | 235 | 0 | 0 | 135 |
| Connector | 817 | -1931 | -1047 | 158 | 558 | 544 | 84 | 100 | 52 |
| Walkway | 1049 | -1801 | -60 | 132 | 583 | 354 | 0 | 56 | 287 |
| Stairs | 182 | -1796 | 1024 | 241 | 584 | 146 | 2 | 0 | 77 |
| Tunnels | 1501 | -1678 | -2113 | 340 | 606 | 749 | 323 | 311 | 0 |
| Water | 1374 | -1397 | 19 | 35 | 660 | 339 | 16 | 222 | 159 |
| Bridge | 166 | -1371 | -243 | 123 | 665 | 389 | 0 | 11 | 51 |
| TSpawn | 665 | -1064 | -2837 | 201 | 724 | 888 | 112 | 172 | 0 |
| Construction | 382 | -974 | -551 | 100 | 742 | 448 | 0 | 94 | 23 |
| Pipe | 188 | -889 | -936 | 22 | 758 | 522 | 54 | 71 | 0 |
| BombsiteB | 1447 | -846 | 168 | 100 | 766 | 310 | 6 | 277 | 183 |
| TStairs | 201 | -843 | -2177 | 266 | 767 | 761 | 27 | 49 | 0 |
| Alley | 1077 | -624 | -1574 | 149 | 809 | 645 | 83 | 408 | 0 |
| Canal | 1428 | -447 | -705 | 23 | 843 | 478 | 143 | 524 | 87 |
| SideAlley | 4 | -324 | -2039 | 149 | 867 | 735 | 2 | 1 | 0 |
