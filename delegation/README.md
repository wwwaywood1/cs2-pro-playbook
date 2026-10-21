# 任务分派板

Claude 负责主线：架构、解析、语义、战术识别，以及审核和合并所有外包结果。
界面和有固定规格的体力活交给 DeepSeek；需要通读代码、跑测试、联网查资料的任务交给 GPT（目前额度充足）。

## 怎么用（自动派活，2026-10 起）

Claude 通过 PAL MCP 直接派活、收结果、落盘、测试、合并，不再需要人工复制粘贴。路由规则：

| 任务类型 | 派给 | 通道 | 不可用时 |
|---|---|---|---|
| 固定格式的文案、配置、命名、翻译、数据整理、第二意见 | deepseek-flash（只用这个 DeepSeek 型号） | PAL `chat` | 在 VT 校园网时 PAL 自动隐藏 DeepSeek，改用 MiniMax-M3.1-Flash |
| 读代码、改代码、跑测试、开 PR | Codex CLI | PAL `clink`（cli_name=codex） | 退回手动：把任务书发给 Codex 网页版 |
| 需要联网查证、带出处 | ChatGPT 网页版 | 手动 | — |
| 看图任务（雷达图标注等） | ChatGPT 网页版 | 手动 | 先试 MiniMax 看图，不行再手动 |

规则：
1. 每次派活前，Claude 先调用 `listmodels`，按当时能用的模型选通道。
2. 外包结果一律由 Claude 跑测试和 CI 检查后再合并，并在下面的审核记录里写一行。
3. PAL `chat` 的回复必须在约 60 秒内返回（桥接超时会丢结果）：给 DeepSeek/MiniMax 的活要小——少量文件、`thinking_mode` minimal/low、要求简短输出。适合：数据核查、代码审查、短文案。大活交给 Codex（它直接写文件，不受这个限制）。
4. 只有走"手动"通道的任务需要你转发：把任务书从分割线开始整段发给对应模型，回复原样贴回给 Claude。

## 任务

| ID | 交给 | 内容 | 依赖 | 优先级 | 状态 |
|---|---|---|---|---|---|
| [DS-01](DS-01_map_callouts.md) | DeepSeek | Inferno 点位映射成区域和路线（之后每张新图重复一次） | 无 | 高：MVP 第二张图 | 完成（Inferno） |
| [DS-02](DS-02_team_aliases.md) | DeepSeek | 职业队名别名表（例如把 `PV` 统一成 PARIVISION） | 无 | 高：批量解析前需要 | 完成 |
| [DS-03](DS-03_i18n_labels.md) | DeepSeek | 网站中英文文案和点位译名 | 无 | 中 | 完成 |
| [DS-04](DS-04_frontend.md) | DeepSeek | 前端 v1，分 A/B/C 三阶段 | DS-03 | 中 | 完成 |
| [GPT-01](GPT-01_robustness_review.md) | GPT (Codex) | 解析层边界情况审查和修复 | 仓库已推到 GitHub | 中：批量解析前做最好 | 完成 |
| [DS-05](DS-05_map_configs.md) | DeepSeek | 其余 5 张图（Nuke、Dust2、Ancient、Anubis、Overpass）的点位映射 + 中英文译名 | 无（任务书已生成） | 高 | 完成 |
| [GPT-02](GPT-02_m2_review.md) | GPT (Codex) | 热力图、选手总结、战术识别三个新模块的代码审查和修复 | Claude 先把战术识别接进导出 | 高 | 完成 |
| [GPT-03](GPT-03_multipart_demos.md) | GPT (Codex) | 支持分段录制的 demo（约 7% 的比赛现在被跳过） | 无 | 中 | 完成 |
| [GPT-04](GPT-04_ci.md) | GPT (Codex) | GitHub Actions：测试、前端构建、浏览器冒烟测试；手动触发的 Pages 部署 | 无 | 中 | 完成 |
| [GPT-05](GPT-05_pro_roles.md) | GPT（联网） | 155 名选手的角色真值表（带出处），用来校准角色标签 | 附件 `delegation/inputs/players_roster.csv` | 高 | 完成 |
| [GPT-06](GPT-06_spot_names.md) | GPT（看图） | Mirage、Inferno 共 108 个道具落点的中英文名字，输出 `config/spots/*.toml` | 附件 `delegation/inputs/spots/`（1 个表 + 4 张图） | 中 | 完成 |
| [DS-06](DS-06_heatmaps.md) | DeepSeek | 战队热力图页面：选战队 → 箭头切换地图 → T/CT → 勾选选手（五色），四种视图，选手总结卡片 | 无（数据、类型、计算函数已就绪） | 高 | 完成 |
| [GPT-07](GPT-07_tactics_page.md) | Codex（PAL 自动派） | 战术套路页面：T/CT 概览、爆弹卡片（小雷达 + 点位名 + 跳转道具库）、队伍页显示统计事实 | 无 | 高 | 完成 |
| M4 战队点评 | MiniMax（Anubis）+ Codex（其余 5 张图），PAL 自动派 | 把每队的统计事实改写成 1–3 句中英文点评，`scripts/insight_text.py check` 校验数字 | 无 | 中 | 完成 |

## 审核记录（Claude）

- **GPT-01**：补丁和 `REVIEW.md` 原样合并。在两场 HLTV 和一场 FACEIT 真实 demo 上验证，没有误杀。追加一处修正：队伍识别检查只看正式回合内的 tick，避免热身阶段的 bot 或临时进出的人导致整场 demo 被拒（GPT 在 REVIEW.md 中已列为遗留风险）。新增 1 条回归测试，共 50 项通过。核实了 awpy 3.1 的刀局与随后回合共用编号，过滤刀局后编号仍从 1 连续，不会误触发"回合不连续"的拒绝。
- **DS-01**：原样采用。用 9z vs PARIVISION 的真实走位核对了存疑点位：T ramp 主要出现在下 B 回合（363:74），Ruins、Arch 是 CT 开局站位。
- **DS-02**：原样采用（101 条别名）。多出的 `confidence` 列不影响加载。
- **DS-03**：改了 2 处：Mirage `Catwalk` 由"A 小道"改为"中路短"（该点在中路、通往 B 一侧）；英文 `times_thrown` 改为 "in {m} matches"。新增 `ui.no_plant`。`SnipersNest` 保留 DeepSeek 的"VIP 狙位"（用户确认的叫法）。
- **DS-04**：干净环境 `npm ci && npm run build` 通过，types.ts 哈希未变，依赖在约束内。新增 `web/e2e/smoke.py`（headless Chromium，24 项检查）全部通过。修了一处：队伍页"下包点分布"里"未下包"一类原来显示为"—"。
- **DS-05**：5 张图的映射和 123 条译名基本采用，`check_map_config.py --all` 七张图全部 OK。按点位表逐个复核了"所在路线与 T 方下包数据相反"的点位，只改 1 处映射：Anubis `Canal` 由 A_APPROACH 改为 MID（下 A 838 次、下 B 537 次，是两边共用的中路水渠，归 A 会把 B 分兵误算成 A 线）。其余存疑点保留 DeepSeek 的判断并留注释：Anubis `PalaceInterior`（以 CT 站位为主，T 方样本少）、Dust2 `MidDoors`（中路转 B 是正常打法）、Overpass `Playground`（位置在 A 侧，只有 246 个样本）、Overpass `Walkway`（CT 轮转通道）。Overpass 数据里没有 CTSpawn 点位，不影响。改了 Dust2 的 5 个中文译名，换成国内常用叫法：Catwalk→A 小道、Hole→B 窗、UpperTunnel→B 洞、LowerTunnel→下水道、OutsideTunnel→B 洞外。前端构建和 24 项冒烟测试通过。

## 待办（下一轮可发）

**GPT 现在可发五件，互不冲突：** Codex 三件（GPT-02 审查新模块、GPT-03 分段 demo、GPT-04 CI），ChatGPT 两件（GPT-05 角色真值表，联网；GPT-06 落点命名，看图）。之后还有一件：网站数据体积控制（道具库只导出用过 2 次以上的道具），等 GPT-02 合并后再写任务书。

**DS-06 战队热力图页面**：把 `delegation/DS-06_heatmaps.md` 从分割线开始发给 DeepSeek，同时上传任务书开头列出的 11 个附件。数据（`samples/site/heatmap_teams.json`、`samples/site/de_mirage/heatmaps/`）、类型（`web/src/types.ts` 末尾）、计算和着色函数（`web/src/heatmap.ts`）都已就绪，DeepSeek 只做界面。效果参考 `scripts/heatmap_preview.py` 生成的图。

现役图池 7 张图的点位映射和译名都已完成。新图进图池时，用 `python scripts/make_map_briefs.py data/raw --brief` 重新生成任务书，流程同 DS-05（模板在 `delegation/templates/DS-05_header.md`）。

- **DS-06**：组件和 i18n 片段原样合并（types/heatmap/data/styles 未动）。用真实多图数据在浏览器里验证：箭头和方向键切图、URL 状态、五色叠加、选手卡片、375px 无横向滚动、控制台无报错。
- **GPT-03**：补丁内容原样合并（Codex 环境没有 Git 远端，交付为内联 diff，由 Claude 落盘）。新增 17 项测试全部通过；DESIGN.md 的说明压缩后合并。真实分段 demo 的端到端测试依赖本地文件，你 Mac 上还没有分段 demo，暂未在本仓库复跑。
- **GPT-04**：PR #1 合并，CI 56 秒通过；Pages 只能手动触发（私有仓库）。
- **GPT-05**：表格存为 `validation/pro_roles.csv`。据此把狙击手标签改为"队内狙最多且 ≥15%，或任何人 ≥40%"：50 名职业狙中找出 49 名，没有误标（原规则只找出 29 名）。自由人标签精度高但漏掉大半，原因写在 DESIGN.md。
- **GPT-06**：108 个落点名字写入 `config/spots/*.toml`（坐标取自原表，不手抄）。爆弹套路现在显示为"楼梯烟 + 丛林烟 + …"、"B区警家烟 + 棺材烟 + B包三箱火"。
- **GPT-02**：PR #3 合并（121 项测试）。CI 失败的原因不在 PR #3：PR #2 新增的 `tests/test_tune_roles.py` 在干净环境里无法导入 `scripts`，Claude 在 `pyproject.toml` 加了 `pythonpath = ["."]` 后 CI 通过。
- **GPT-06 续（Nuke、Dust2、Ancient、Anubis）**：ChatGPT 交付 230 个落点名字，其中 8 个标为低置信度。已写入 `config/spots/`，ID 无重复、中英文齐全，测试通过。

- **GPT-07**：第一次经 PAL 自动派给 Codex。7 个文件原样采用：TypeScript 编译一次通过，用 Nuke 真实数据在浏览器里检查了卡片、雷达标记、A/B 筛选、排序、跳转道具库和 375px 宽度，24 项冒烟测试通过，控制台无报错。

- **M4 战队点评**：105 支队伍（6 张图）的点评全部通过校验：每个数字都出自所引用的事实，引用的事实编号都存在，长度在限制内。点评带事实指纹，事实变了导出时自动丢弃旧点评。DeepSeek 当时在校园网连不上，Anubis 改由 MiniMax 写；为免逐条转存，其余 5 张图交给 Codex 在 Mac 上直接写稿并自跑校验。

- **MiniMax 数据核查（2026-10-21）**：发现跨来源重复比赛（HF 与 HLTV 同一场被解析两次，Falcons Mirage 17 行里 4 场重复），已派 GPT-15 修复。代码审查发现 `web/src/motion.ts` pointermove 里同步读布局（应合并到 rAF），留给下一轮前端修改。

## 为什么这样分

- DS-01/02/03 靠 CS 常识就能完成，输出是固定格式的配置或文案，Claude 审核成本低。
- DS-04 工作量大，但规格已经写死：数据类型由 Claude 提供，验收标准明确。DeepSeek 写代码，Claude 编译、测试、修错。
- GPT-01/02/03/04 需要通读代码、构造边界情况、跑测试，是推理密集型任务，交给 Codex。GPT-05 需要联网查证，带出处。
- 战术识别（M2）、角色阈值校准、数据管线改动留给 Claude，这部分的设计和验证不适合外包。
