# 任务分派板

Claude 负责主线：架构、解析、语义、战术识别，以及审核和合并所有外包结果。
体力活交给 DeepSeek。GPT 额度紧张，只承担一件需要读代码、跑测试的审查任务。

## 怎么用

1. 打开对应的任务书，从分割线开始**整段**复制给对应模型；有附件的按任务书说明上传。
2. 把模型的回复**原样**贴回给 Claude，不用自己改。
3. Claude 负责落盘、跑测试、修错、合并，并把这张表的状态更新为“完成”。

## 任务

| ID | 交给 | 内容 | 依赖 | 优先级 | 状态 |
|---|---|---|---|---|---|
| [DS-01](DS-01_map_callouts.md) | DeepSeek | Inferno 点位映射成区域和路线（之后每张新图重复一次） | 无 | 高：MVP 第二张图 | 完成（Inferno） |
| [DS-02](DS-02_team_aliases.md) | DeepSeek | 职业队名别名表（例如把 `PV` 统一成 PARIVISION） | 无 | 高：批量解析前需要 | 完成 |
| [DS-03](DS-03_i18n_labels.md) | DeepSeek | 网站中英文文案和点位译名 | 无 | 中 | 完成 |
| [DS-04](DS-04_frontend.md) | DeepSeek | 前端 v1，分 A/B/C 三阶段 | DS-03 | 中 | 完成 |
| [GPT-01](GPT-01_robustness_review.md) | GPT (Codex) | 解析层边界情况审查和修复 | 仓库已推到 GitHub | 中：批量解析前做最好 | 完成 |
| [DS-05](DS-05_map_configs.md) | DeepSeek | 其余 5 张图（Nuke、Dust2、Ancient、Anubis、Overpass）的点位映射 + 中英文译名 | 无（任务书已生成） | 高 | 完成 |
| [DS-06](DS-06_heatmaps.md) | DeepSeek | 战队热力图页面：选战队 → 箭头切换地图 → T/CT → 勾选选手（五色），四种视图，选手总结卡片 | 无（数据、类型、计算函数已就绪） | 高 | 待发 |

## 审核记录（Claude）

- **GPT-01**：补丁和 `REVIEW.md` 原样合并。在两场 HLTV 和一场 FACEIT 真实 demo 上验证，没有误杀。追加一处修正：队伍识别检查只看正式回合内的 tick，避免热身阶段的 bot 或临时进出的人导致整场 demo 被拒（GPT 在 REVIEW.md 中已列为遗留风险）。新增 1 条回归测试，共 50 项通过。核实了 awpy 3.1 的刀局与随后回合共用编号，过滤刀局后编号仍从 1 连续，不会误触发"回合不连续"的拒绝。
- **DS-01**：原样采用。用 9z vs PARIVISION 的真实走位核对了存疑点位：T ramp 主要出现在下 B 回合（363:74），Ruins、Arch 是 CT 开局站位。
- **DS-02**：原样采用（101 条别名）。多出的 `confidence` 列不影响加载。
- **DS-03**：改了 2 处：Mirage `Catwalk` 由"A 小道"改为"中路短"（该点在中路、通往 B 一侧）；英文 `times_thrown` 改为 "in {m} matches"。新增 `ui.no_plant`。`SnipersNest` 保留 DeepSeek 的"VIP 狙位"（用户确认的叫法）。
- **DS-04**：干净环境 `npm ci && npm run build` 通过，types.ts 哈希未变，依赖在约束内。新增 `web/e2e/smoke.py`（headless Chromium，24 项检查）全部通过。修了一处：队伍页"下包点分布"里"未下包"一类原来显示为"—"。
- **DS-05**：5 张图的映射和 123 条译名基本采用，`check_map_config.py --all` 七张图全部 OK。按点位表逐个复核了"所在路线与 T 方下包数据相反"的点位，只改 1 处映射：Anubis `Canal` 由 A_APPROACH 改为 MID（下 A 838 次、下 B 537 次，是两边共用的中路水渠，归 A 会把 B 分兵误算成 A 线）。其余存疑点保留 DeepSeek 的判断并留注释：Anubis `PalaceInterior`（以 CT 站位为主，T 方样本少）、Dust2 `MidDoors`（中路转 B 是正常打法）、Overpass `Playground`（位置在 A 侧，只有 246 个样本）、Overpass `Walkway`（CT 轮转通道）。Overpass 数据里没有 CTSpawn 点位，不影响。改了 Dust2 的 5 个中文译名，换成国内常用叫法：Catwalk→A 小道、Hole→B 窗、UpperTunnel→B 洞、LowerTunnel→下水道、OutsideTunnel→B 洞外。前端构建和 24 项冒烟测试通过。

## 待办（下一轮可发）

**DS-06 战队热力图页面**：把 `delegation/DS-06_heatmaps.md` 从分割线开始发给 DeepSeek，同时上传任务书开头列出的 11 个附件。数据（`samples/site/heatmap_teams.json`、`samples/site/de_mirage/heatmaps/`）、类型（`web/src/types.ts` 末尾）、计算和着色函数（`web/src/heatmap.ts`）都已就绪，DeepSeek 只做界面。效果参考 `scripts/heatmap_preview.py` 生成的图。

现役图池 7 张图的点位映射和译名都已完成。新图进图池时，用 `python scripts/make_map_briefs.py data/raw --brief` 重新生成任务书，流程同 DS-05（模板在 `delegation/templates/DS-05_header.md`）。

## 为什么这样分

- DS-01/02/03 靠 CS 常识就能完成，输出是固定格式的配置或文案，Claude 审核成本低。
- DS-04 工作量大，但规格已经写死：数据类型由 Claude 提供，验收标准明确。DeepSeek 写代码，Claude 编译、测试、修错。
- GPT-01 需要通读代码、构造边界情况、跑测试，是推理密集型任务，交给 Codex 一次做完，省额度。
- 战术识别（M2）、角色阈值校准、数据管线改动留给 Claude，这部分的设计和验证不适合外包。
