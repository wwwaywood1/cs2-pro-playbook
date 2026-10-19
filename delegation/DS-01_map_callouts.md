# DS-01：地图 callout → 区域映射（交给 DeepSeek）

> 用法：把本文件**从下面的分割线开始整段**粘贴给 DeepSeek。它的回复原样贴回给 Claude 审核。
> 一次只做一张图。第一张是 Inferno（输入已附在下面）。其他图需要你先下载该图的 demo，运行
> `python -m playbook callouts 路径/xxx.dem`，再把输出表格替换到“输入”一节。

---

你是一名熟悉 CS2 职业比赛和地图点位的数据工程师。我在做一个开源项目，从职业比赛 demo 中自动分析队伍战术。需要你为一张地图写一份配置文件，把游戏内的点位名称（callout）归到区域（region），再把区域归到路线（lane）。

## 背景

- demo 里每个玩家每一刻都有一个游戏内置的点位名，例如 `BombsiteA`、`Banana`。下面给出该地图全部点位名，以及每个点位的中位坐标 (x, y, z)。
- 区域（region）是中间一层，路线（lane）是最粗的一层，用来生成站位指纹，比如 T 方 30 秒时“A2 M2 B1”。
- lane 只能取这 5 个值之一：`T_SPAWN`、`A`、`MID`、`B`、`CT_SPAWN`。
- region 推荐沿用这 7 个：`T_SPAWN`、`A_APPROACH`（T 方进攻 A 的通道）、`A_SITE`（A 包点及 CT 防守 A 的位置）、`MID`、`B_APPROACH`、`B_SITE`、`CT_SPAWN`。如果这张图确实需要别的划分（例如 Nuke 的上下层），可以新增 region，但每个 region 仍然必须对应上面 5 个 lane 之一，并用注释说明理由。

## 参考样例（Mirage，已经过人工核对）

```toml
map = "de_mirage"
display_name = "Mirage"

[radar]
pos_x = -3230.0
pos_y = 1713.0
scale = 5.0

[regions]
T_SPAWN = "T_SPAWN"
A_APPROACH = "A"
A_SITE = "A"
MID = "MID"
B_APPROACH = "B"
B_SITE = "B"
CT_SPAWN = "CT_SPAWN"

[callouts]
TSpawn = "T_SPAWN"
PalaceAlley = "A_APPROACH"
PalaceInterior = "A_APPROACH"
Scaffolding = "A_APPROACH"
TRamp = "A_APPROACH"
BombsiteA = "A_SITE"
Stairs = "A_SITE"
Jungle = "A_SITE"
Connector = "A_SITE"
TopofMid = "MID"
Middle = "MID"
Catwalk = "MID"
Ladder = "MID"
SnipersNest = "MID"
Underpass = "MID"
SideAlley = "B_APPROACH"
House = "B_APPROACH"
BackAlley = "B_APPROACH"
Apartments = "B_APPROACH"
BombsiteB = "B_SITE"
Shop = "B_SITE"
Truck = "B_SITE"
CTSpawn = "CT_SPAWN"
```

## 输入：de_inferno 的全部点位（来自 9z vs PARIVISION 职业比赛 demo）

| callout | samples | x | y | z |
|---|---|---|---|---|
| TSpawn | 233924 | -1657 | 420 | -64 |
| LowerMid | 32957 | -616 | 617 | -7 |
| Upstairs | 3344 | -521 | 218 | 192 |
| Bridge | 2284 | -413 | -122 | 192 |
| Kitchen | 1370 | -166 | 288 | 192 |
| TRamp | 38995 | -140 | 899 | 53 |
| Deck | 4007 | 15 | 41 | 208 |
| Underpass | 12234 | 289 | 656 | 19 |
| Banana | 395169 | 457 | 1888 | 136 |
| BombsiteB | 358076 | 583 | 2765 | 161 |
| SecondMid | 43870 | 658 | -89 | 89 |
| Middle | 118981 | 726 | 600 | 96 |
| BackAlley | 10786 | 867 | -600 | 89 |
| Ruins | 96382 | 1202 | 2822 | 128 |
| Apartments | 100140 | 1252 | -281 | 256 |
| TopofMid | 89520 | 1431 | 208 | 132 |
| Quad | 21408 | 1459 | -50 | 132 |
| Arch | 46630 | 1813 | 1213 | 164 |
| BombsiteA | 257159 | 2036 | 296 | 160 |
| Balcony | 37557 | 2088 | -260 | 290 |
| CTSpawn | 304360 | 2353 | 2079 | 135 |
| Pit | 50867 | 2491 | -139 | 97 |
| Library | 43920 | 2571 | 1203 | 160 |

注意：同名点位在不同地图上含义不同。例如 Inferno 的 `Apartments` 在 A 区一侧，Mirage 的 `Apartments` 在 B 区一侧。请按这张图的实际位置判断，并参考坐标（T 家和 CT 家的位置在表中已知）。

## 你的输出（严格遵守）

1. 只输出**一个** ```toml 代码块，内容是完整的 `config/maps/de_inferno.toml`。头部和 `[radar]` 保持如下不变：
   ```toml
   map = "de_inferno"
   display_name = "Inferno"

   [radar]
   pos_x = -2087.0
   pos_y = 3870.0
   scale = 4.9
   ```
2. `[callouts]` 必须**恰好**包含上表 23 个点位，一个不多、一个不少，名字大小写和原表完全一致。
3. 拿不准的点位，在该行行尾加注释 `# ?` 并写一句理由，例如 `Arch = "A_SITE"  # ? 连接 CT 家与 A 包点，CT 回防常经过`。
4. 代码块之后，用不超过 5 行列出你拿不准的点位和理由。

## 自检清单（输出前逐条检查）

- [ ] 23 个 callout 全部出现，名称拼写与表格一致
- [ ] 每个 callout 的值都是 `[regions]` 中定义过的 region
- [ ] 每个 region 的值都是 5 个 lane 之一
- [ ] `BombsiteA` → A 侧 region，`BombsiteB` → B 侧 region，`TSpawn` → T_SPAWN，`CTSpawn` → CT_SPAWN
- [ ] 没有编造表格里不存在的 callout
