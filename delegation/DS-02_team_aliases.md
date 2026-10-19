# DS-02：职业队伍名称别名表（交给 DeepSeek）

> 用法：从分割线开始整段粘贴给 DeepSeek，把它返回的 CSV 原样贴回给 Claude。

---

你是熟悉 CS2 职业圈的数据工程师。我在做一个开源项目，从职业比赛 demo 中分析队伍战术。同一支队伍在不同数据源里名字不一样，需要你写一张别名映射表，把各种写法统一成一个标准名。

## 背景

同一支队伍会以这几种形式出现：

- demo 文件里的游戏内队名（clan name），可能是全名，也可能是缩写。已见过的真实例子：`Team Vitality`、`B8 Esports`、`9z`、`PV`（即 PARIVISION）。
- 数据集文件名里的 slug，全小写、用连字符，例如 `natus-vincere`、`the-mongolz`。
- HLTV 上的队名，例如 `Natus Vincere`、`The MongolZ`。

## 你的任务

为 2025 到 2026 年活跃的 Tier 1 / Tier 2 职业 CS2 队伍（约 40 支，优先排名靠前的队伍）写别名表。

- `canonical`（标准名）：使用该队在 HLTV 队伍页面上的显示名，例如 `Vitality`、`Natus Vincere`、`The MongolZ`、`FaZe`、`MOUZ`、`Spirit`、`Falcons`、`FURIA`、`Aurora`、`G2`、`B8`、`9z`、`PARIVISION`。
- `alias`：该队可能出现的每一种写法各占一行，包括：
  - 标准名本身
  - 带组织前缀或后缀的全称，例如 `Team Vitality`、`B8 Esports`、`Team Spirit`、`FaZe Clan`
  - 游戏内常见缩写，例如 `NaVi`、`PV`
  - slug 形式，例如 `natus-vincere`、`the-mongolz`
- 匹配时不区分大小写，所以同一写法不要只因大小写不同就重复列出。

## 输出格式（严格遵守）

只输出**一个** ```csv 代码块，表头和列如下，每行一个别名：

```csv
alias,canonical,confidence
Team Vitality,Vitality,high
vitality,Vitality,high
B8 Esports,B8,high
PV,PARIVISION,high
```

- `confidence` 取 `high` 或 `low`。不确定的缩写，或不确定该队 2026 年是否仍然活跃时，标 `low`。
- 不要为了凑数编造缩写。宁可少列，也不要列错。
- 同一个 alias 不能映射到两个不同的 canonical。

代码块之后，用不超过 5 行说明你标了 `low` 的条目和原因。

## 自检清单

- [ ] 上面 4 个真实例子（Team Vitality、B8 Esports、9z、PV）都已包含
- [ ] 以下 slug 都有对应条目：vitality, mouz, spirit, falcons, furia, the-mongolz, aurora, natus-vincere, faze, g2
- [ ] 没有重复的 alias，也没有一个 alias 对应多个 canonical
- [ ] 每行恰好 3 列，没有多余的逗号
