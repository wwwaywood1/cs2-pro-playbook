# GPT-01 解析层健壮性审查

## 数据契约与行为变化

**未修改任何表的列名、列含义或 Site JSON contract；未新增项目依赖。**

修复后的 `is_opening` 在同 tick 并列时按输入事件顺序只选一条；这是“首个双方击杀”定义的确定性实现，不声称能恢复 sub-tick 真实先后。平分比赛的 `matches.winner` 为 null，不再任意指定一队。

新增保守拒绝策略：遇到可观察到的回合重复/倒退/缺号、非第 1 回合起始、时间范围冲突、未知胜方、无法识别的玩家或队伍时抛出 `ValueError`，不产出伪造的完整比赛结果。steamid 0/null 的在场玩家、冻结结束缺少一方、冲突队名同样拒绝。这是**防止错误输出，不是完整支持回档、机器人或残缺 demo**。不自动去重回合，也不推算未知比分。

审查先阅读 DESIGN.md，再检查 parse.py、semantics.py、utility.py 及现有测试。仅修改 parse.py、utility.py，并新增 tests/test_robustness.py；没有风格重构或符号重命名。

## 指定的十项检查

| # | 场景 | 结论 | 证据、影响及处理 |
|---|---|---|---|
| 1 | 技术暂停与备份恢复 | **真实防护缺陷；上游实际回档行为 unverifiable** | 原代码按 round_num 排序并累计胜场，重复编号会重复加分；相同编号的 positions 会混合不同时间段，asof 只按起始 tick 选择，并不撤销已作废回合。合成 `(1,1)`、`(1,2,1)`、重叠区间均已加入拒绝测试。合法相邻回合可共享 official_end/start tick，该 tick 归下一回合。不含恢复事件的 Mirage 不足以证明 awpy 3.1 在真实 restore 后会重复或倒退；如果它重新连续编号并隐藏恢复，当前防护无法检测。 |
| 2 | MR3 加时 | **non-issue（完整、正确编号的输入）** | half_of 在 25–27/28–30/31–33 分别为 3/4/5；没有把加时硬编码为每 12 局换边。side 来自每回合冻结结束位置；score 字典按队伍而非阵营累计，换边不重置。合成测试覆盖 1/13/25/28/31 的队伍换边及 half；未获取真实 OT demo，因此不声称 OT 端到端验证。 |
| 3 | 替补、重连、错误末次阵营、缺 clan | **真实 bug，已修复** | 旧 roster 过滤会丢弃最终为 spectator 的参赛者；首回合之外加入的无 clan 玩家没有 team，部分缺 clan 则会产生第三个队名。现在按各回合冻结结束同阵营关系连接队友，传播已有 clan 或统一 fallback；忽略 roster 最后 side。测试包含 spectator roster、缺 clan、round 13 替补、后续重连与换边。整队替换无队友衔接、从未在 freeze end 出现等歧义会明确拒绝。 |
| 4 | bots / steamid 0 | **真实 bug，已防护** | 旧 steamid 字典会把多个 bot 合并，后续 player joins 还可能倍增行数。保持现有 player key 契约，因此拒绝 tk 中在场的 0/null ID，而不生成假 Steam ID。纯观战 GOTV 的 roster 0 不触发该检查，真实 fixture 已验证。 |
| 5 | 无 clan 的 fallback | **完整原阵容换边 non-issue；部分缺名真实 bug** | 原 fallback 对首局玩家存为固定 steamid 映射，所以换边本身不会改名，两个纯 fallback 标签本身也不同。问题是有名/无名队友分裂，或双方 clan 归一化后同名。新队友分组统一标签，同名和组内冲突明确报错；全缺 clan 测试确认跨半场与加时仍是两个稳定标签。 |
| 6 | GOTV 中途开始 | **真实 bug，已部分防护；隐式重编号 unverifiable** | 原 score 从 0 开始，把不完整比赛当完整比分；first_fe 只能代表第一条观测，不能说明真实首发阵营。输入从第 6 局开始现在拒绝，跳号同理。若 awpy 把中途开始重编号成 1，则仅靠当前 tables 无法识别，需要原始服务器比分/完整性信号。尾部截断同样不能仅靠连续回合编号检测。 |
| 7 | 128 / 非 64 tick | **窗口真实 bug，已修复；采样 non-issue（整数 tick rate）** | positions 本来用 `round(rate * SAMPLE_SECONDS)`，t_s 也除以 rate，128 tick 不会变成两倍采样频率。道具旧 32 tick 在 128 tick 只等于 0.25 秒；现按 rate 缩放到 0.5 秒。50 tick 延迟在 64 时不匹配、128 时匹配，已测试。非整数 tick rate 的每秒取整会累积少量偏移，未验证这类 demo，不作支持保证。 |
| 8 | 邻近同类道具并发投掷 | **真实 bug，已修复可证实部分；无身份数据仍有歧义** | 合成案例：两名队友同 tick 投烟，首轨迹点距 A 0 单位、距 B 10 单位，而 awpy_thrower 明确是 B。旧贪心选择 A，还用 steamid 覆盖正确身份。现在候选必须符合已知 awpy_thrower；无候选时保留该身份、matched=false。没有已知身份时仍采用原一对一近邻策略；仅凭近邻/先后无法证明真实投手，未擅自加入角度或速度阈值。 |
| 9 | TK/world/bomb 先死、同 tick 首杀 | **TK/world 过滤 non-issue；同 tick 真实 bug，已修复** | 旧 duel 排除 teamkill 和无 attacker team 的 world/bomb death，但用最小 tick 相等判断会标记两条 opening。semantics 的 opening join 随之把 team_rounds 复制，影响 player_rounds。现按稳定事件顺序唯一选择，且排除 freeze 前、post-round 和未知 victim team；无有效 duel 时全为 false。测试将这些情况组合覆盖。 |
| 10 | freeze end 只有一侧，pivot | **真实 bug，已防护** | 若整份 positions 从未出现某一侧，rename 会找不到列；若仅个别回合缺一侧，则该队/胜方可能为 null，score 循环漏计。现在每回合先检查两侧均可识别且分别属于不同队，再进行 pivot；缺一侧测试验证明确失败，不猜测另一个队或填 0 比分。 |

## 其他问题（按影响排序）

1. **中：平分结果任意选冠军，已修复。** 原 `max(final, key=final.get)` 在 12–12 时按字典顺序选一队。现在平分返回 null；回归测试覆盖平分、正常胜负、空输入。无法据此判断 demo 是否完整结束。
2. **中：空 callout 索引导致崩溃，已修复。** 无地点标签时 NumPy 空掩码不是 bool，或者后续 argmin 无候选。现在使用 bool 掩码并返回未知地点 null；合成空帧测试通过。不以虚构 callout 填充。
3. **低：无符号 tick 减窗口下溢，已修复。** 若未来上游 tick 为 UInt32，开局 tick 10 减 32 可排除合法候选。先转 Int64 再减；tick 10 / shot 5 的 UInt32 回归测试通过。

## 保留的限制与后续所需证据

- 真正的 `mp_backup_restore_load_file` 和 late-join demo 仍需采集。需要比较原始事件/服务器比分与 awpy 输出；当前环境安装的 awpy 核心为编译扩展，不能从其 Python 包证明恢复事件的处理语义。
- 无 thrower 身份的近邻投掷仍可能错配；当前 fixture 的 >95% matched 只证明匹配覆盖率，不证明每个匹配的真实正确性。
- 严格的队友关系检查可能拒绝特殊但有效的阵容变动；其目的是保持 demo×steamid 单一队伍契约下的数据可靠性。检查使用所有 team_num 2/3 的 ticks，热身中出现的 bot 或未知玩家也可能导致拒绝。
- 不改动 `semantics.py`：它依赖 parse 层唯一首杀及无碰撞的玩家/回合键。已有错误 parquet 不会自动修复，需重新解析源 demo；只重新运行 export 不足以应用本补丁。
- 未新增依赖；测试环境安装项目声明的依赖及 dev extra。没有 Git 元数据，故不创建 commit；另交付可应用于原目录副本的单一 unified patch。

## 验证

已成功下载 README 指定的真实 Mirage demo（B8 vs Vitality），不是跳过端到端测试。SHA256：

`321cfe8bd30501f9040a9ae0cfaca900b6db1cc6cc6ab026f56b86a5b3e20ddc`

环境：Python 3.14、awpy 3.1.0、polars 2.0.0、pytest 9.1.1。于仓库根目录使用隔离虚拟环境执行 `pytest -q`。包含原有 7 个单元测试、9 个真实 demo 端到端测试及本次新增回归用例。最终输出：

```text
.................................................                        [100%]
49 passed in 7.78s
```
