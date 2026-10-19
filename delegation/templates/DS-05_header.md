# DS-05：其余地图的点位映射 + 中英文译名（交给 DeepSeek）

> 本文件由 `scripts/make_map_briefs.py --brief` 生成，表格来自真实职业比赛 demo。不要手改表格；要更新时重新运行脚本。
>
> 用法：把本文件**从下面的分割线开始整段**发给 DeepSeek（DSH 工作区能直接读写仓库文件）。它改完文件后，把回复里的"交付报告"一节原样贴给 Claude 审核。

---

你是熟悉 CS2 职业比赛和地图点位的数据工程师。我们在做开源项目 cs2-pro-playbook：从职业比赛 demo 中自动分析战术。这一轮请你为这些地图完成两件事：{MAPS}

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
python3 scripts/check_map_config.py {MAP_ARGS}
```

每张图都要输出 `OK`。出现 `FAIL` 就按提示修改后重新运行，直到全部通过。

## 4. 交付报告（回复格式）

只需回复下面三部分，**不要**贴文件全文：

1. 自检命令的完整输出。
2. 每张图拿不准的点位：最多 5 行，写明点位名、你的归类和理由，要引用表格里的数据。
3. 你新增的区域（如果有）及理由。
