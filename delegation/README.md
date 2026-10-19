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
| [DS-05](DS-05_map_configs.md) | DeepSeek | 其余 5 张图（Nuke、Dust2、Ancient、Anubis、Overpass）的点位映射 + 中英文译名 | 无（任务书已生成） | 高 | 已发 |

## 审核记录（Claude）

- **GPT-01**：补丁和 `REVIEW.md` 原样合并。在两场 HLTV 和一场 FACEIT 真实 demo 上验证，没有误杀。追加一处修正：队伍识别检查只看正式回合内的 tick，避免热身阶段的 bot 或临时进出的人导致整场 demo 被拒（GPT 在 REVIEW.md 中已列为遗留风险）。新增 1 条回归测试，共 50 项通过。核实了 awpy 3.1 的刀局与随后回合共用编号，过滤刀局后编号仍从 1 连续，不会误触发"回合不连续"的拒绝。
- **DS-01**：原样采用。用 9z vs PARIVISION 的真实走位核对了存疑点位：T ramp 主要出现在下 B 回合（363:74），Ruins、Arch 是 CT 开局站位。
- **DS-02**：原样采用（101 条别名）。多出的 `confidence` 列不影响加载。
- **DS-03**：改了 2 处：Mirage `Catwalk` 由"A 小道"改为"中路短"（该点在中路、通往 B 一侧）；英文 `times_thrown` 改为 "in {m} matches"。新增 `ui.no_plant`。`SnipersNest` 保留 DeepSeek 的"VIP 狙位"（用户确认的叫法）。
- **DS-04**：干净环境 `npm ci && npm run build` 通过，types.ts 哈希未变，依赖在约束内。新增 `web/e2e/smoke.py`（headless Chromium，24 项检查）全部通过。修了一处：队伍页"下包点分布"里"未下包"一类原来显示为"—"。

## 待办（下一轮可发）

**DS-05：其余 5 张图（Nuke、Dust2、Ancient、Anubis、Overpass）的点位映射 + 中英文译名**，合并了原来的"DS-01 继续"和"DS-03 补充"。现役图池共 7 张，Train 和 Vertigo 不在其中，不做。

任务书 `delegation/DS-05_map_configs.md` 由脚本根据真实 demo 生成，每张图都附点位表（坐标、雷达像素、T 方下 A/下 B 时经过的次数、CT 开局站位）和要改的确切文件路径。生成步骤：

1. 下载第一批 demo，里面包含这 5 张图各 1 场：`python3 scripts/download_batch1.py`
2. 生成点位表和任务书：`python scripts/make_map_briefs.py data/raw --brief`。输出到 `delegation/inputs/<map>_callouts.csv` 和 `delegation/DS-05_map_configs.md`
3. 把 `delegation/DS-05_map_configs.md` 从分割线开始发给 DeepSeek
4. DeepSeek 改完后，自检命令 `python3 scripts/check_map_config.py de_nuke de_dust2 de_ancient de_anubis de_overpass` 必须全部输出 OK；Claude 再按点位表数据复核

模板在 `delegation/templates/DS-05_header.md`。Mirage 和 Inferno 的点位表已生成，`python3 scripts/check_map_config.py --all` 对这两张图都通过。

## 为什么这样分

- DS-01/02/03 靠 CS 常识就能完成，输出是固定格式的配置或文案，Claude 审核成本低。
- DS-04 工作量大，但规格已经写死：数据类型由 Claude 提供，验收标准明确。DeepSeek 写代码，Claude 编译、测试、修错。
- GPT-01 需要通读代码、构造边界情况、跑测试，是推理密集型任务，交给 Codex 一次做完，省额度。
- 战术识别（M2）、角色阈值校准、数据管线改动留给 Claude，这部分的设计和验证不适合外包。
