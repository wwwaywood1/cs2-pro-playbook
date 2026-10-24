import { useState } from "react";
import { getAILab, getCTPatterns, getReplayIndex, useData, assetUrl } from "../data";
import { fmtPct } from "../format";
import type { AILab as LabData, RoundRef } from "../labTypes";
import CTTrajectories, { CT_COLORS } from "../components/CTTrajectories";
import { ReplayButton } from "../components/RoundReplay";
import { ErrorNotice, Loading } from "../components/Status";
import { signedPP } from "../components/CTDefense";
import "../lab.css";

const GROUPS: Record<string, string> = { alive_diff: "人数差", hp_equipment: "血量与装备", map_control: "区域占位输入", bomb_state_time: "C4 与倒计时", active_utility: "场上道具", positional_spread_pinch: "分散与夹击" };
const PHASES: Record<string, string> = { round_start: "开局", before_execute: "进点前", after_plant: "下包后" };

// Translate exported explanatory copy at the presentation boundary; preserve data and citations.
const LAB_COPY_ZH: Record<string, string> = {
  "TAGNet was validated on Dust2 only (697 rounds); this project applies a lightweight method to all parsed maps. Results below are computed from our demos.": "TAGNet 仅在 Dust2 上进行了验证（697 个回合）；本项目将轻量方法应用于所有已解析地图。下方结果均由本项目的比赛录像计算得出。",
  "Distance kernel, not learned attention; self edges included; tau=0.25": "基于距离的核权重，并非学习得到的注意力；包含自连接；温度参数 τ=0.25",
  "Existing model uses lane occupancies as spatial inputs; replay t_control is observed separately and is not a model feature.": "现有模型以通道占位作为空间输入；回放中的 T 控图率是独立观测指标，不属于模型特征。",
  "Active utility and positional spread/pinch are not inputs to the existing model and have zero attribution.": "场上道具、站位分散与夹击均未作为现有模型的输入，因此归因为零。",
  "Map and pre-round score are held fixed; background size is capped at 32 to bound export runtime.": "地图与回合开始前的比分保持固定；背景样本最多为 32 个，以限制导出耗时。",
  "Explains calibrated match-held-out model, not a separately trained surrogate.": "归因解释的是经过校准、按比赛留出的模型，并非另外训练的替代模型。",
  "Existing occupied 15x15 XY replay grid; straight-line nearest-player distances, no NavMesh or walls": "使用现有回放中有观测的 15×15 XY 网格，按最近玩家的直线距离计算；不包含导航网格或墙体",
};
const METHOD_ZH: Record<string, string> = {
  lightweight_standardised_pca_kmeans: "轻量标准化、主成分分析与 K 均值聚类",
  exact_interventional_group_shapley_64_coalitions: "精确干预式分组 Shapley 归因（64 种组合作用）",
  existing_hist_gradient_boosting_match_oof_plus_isotonic: "现有直方图梯度提升模型，按比赛留出预测并进行保序校准",
};
const labCopy = (value: string) => LAB_COPY_ZH[value] ?? value;
function Method({ value }: { value: string }) {
  return <>{METHOD_ZH[value] ?? "方法标识"}（<code>{value}</code>）</>;
}
const economyLabel = (value: string) => ({ eco: "经济局", force: "强起", full: "全装", full_buy: "全装", pistol: "手枪局", mixed: "混合配装" }[value] ?? value);

function Attention({ data }: { data: LabData }) {
  const [map, setMap] = useState("de_mirage");
  const [clusterId, setClusterId] = useState("");
  const [time, setTime] = useState(0);
  const [floor, setFloor] = useState(0);
  const [point, setPoint] = useState<(RoundRef & { cluster_id: string }) | null>(null);
  const patterns = useData(() => getCTPatterns(map), [map]);
  const replays = useData(() => getReplayIndex(map), [map]);
  const examples = data.attention.filter(a => a.map === map);
  const example = examples.find(a => a.cluster_id === clusterId) ?? examples[0];
  const snapshot = example?.snapshots[Math.min(time, example.snapshots.length - 1)];
  const cloud = patterns.data?.embedding.points ?? [];
  const minX = Math.min(...cloud.map(p => p.x)), maxX = Math.max(...cloud.map(p => p.x));
  const minY = Math.min(...cloud.map(p => p.y)), maxY = Math.max(...cloud.map(p => p.y));
  const round = point ?? example?.round;
  return <section className="lab-panel panel" data-lab-panel="attention" aria-labelledby="lab-attention-title">
    <p className="eyebrow">01 / 阵型</p><h2 id="lab-attention-title">时空距离核 · CT 阵型沙盘</h2>
    <div className="lab-controls"><label>地图 <select value={map} onChange={e => { setMap(e.target.value); setClusterId(""); setTime(0); setFloor(0); setPoint(null); }}>{[...new Set(data.attention.map(a => a.map))].map(m => <option key={m} value={m}>{m}{m === "de_overpass" ? "（历史）" : ""}</option>)}</select></label>
      <label>阵型 <select value={example?.cluster_id ?? ""} onChange={e => { setClusterId(e.target.value); setPoint(null); }}>{examples.map(a => <option key={a.cluster_id} value={a.cluster_id}>{a.cluster_id} · {patterns.data?.clusters.find(c => c.id === a.cluster_id)?.label_zh ?? a.round.team}</option>)}</select></label>
      {map === "de_nuke" && <label>楼层 <select value={floor} onChange={e => setFloor(Number(e.target.value))}><option value="0">上层</option><option value="1">下层</option></select></label>}</div>
    <p className="lab-method">{labCopy(data.metadata.attention)} · αᵢⱼ = softmaxⱼ(exp(−dᵢⱼ / 4215.87 / τ)) · τ={example?.tau}。行归一化包含自连接；图中自连接以节点圆环表示。</p>
    {snapshot ? <><label className="lab-slider">冻结结束后 {snapshot.t_s} 秒 <input aria-label="阵型快照" type="range" min="0" max={example.snapshots.length - 1} value={Math.min(time, example.snapshots.length - 1)} onChange={e => setTime(Number(e.target.value))} /></label>
      <div className="lab-attention-grid"><svg className="lab-radar" viewBox="0 0 1024 1024" role="img" aria-label={`${map} ${example.cluster_id} 距离核`}>
        <image href={assetUrl(`radars/${map}${map === "de_nuke" && floor === 1 ? "_lower" : ""}.png`)} width="1024" height="1024" />
        <CTTrajectories snapshots={example.snapshots.filter(s => s.t_s <= snapshot.t_s)} level={floor} kind="medoid" />
        {snapshot.positions.map((p, i) => p[2] === floor && <g key={i}>{snapshot.positions.map((q, j) => i !== j && q[2] === floor && <line key={j} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} stroke="#6edcd0" strokeWidth={snapshot.alpha[i][j] * 22} opacity={snapshot.alpha[i][j] * 2.2}><title>α{ i + 1 }→{ j + 1 } = {snapshot.alpha[i][j].toFixed(4)}</title></line>)}<circle cx={p[0]} cy={p[1]} r={12 + snapshot.alpha[i][i] * 15} fill="#08151f" stroke={CT_COLORS[i]} strokeWidth="5" /><text x={p[0]} y={p[1] + 5} textAnchor="middle" fill="white" fontSize="17">{i + 1}</text></g>)}
      </svg><div><h3>PCA 二维投影 · 本图完整样本</h3>{patterns.error ? <p role="status">阵型投影加载失败。</p> : <svg className="lab-cloud" viewBox="0 0 400 340" role="group" aria-label="CT 阵型 PCA 投影">{cloud.map((p, i) => <circle key={i} cx={20 + (p.x - minX) / (maxX - minX || 1) * 360} cy={320 - (p.y - minY) / (maxY - minY || 1) * 300} r={p.cluster_id === example.cluster_id ? 3.5 : 2.5} fill={CT_COLORS[Number(p.cluster_id.slice(1)) % CT_COLORS.length]} opacity={p.cluster_id === example.cluster_id ? .85 : .3} role="button" aria-label={`${p.cluster_id} ${p.team} R${p.round_num}`} onClick={() => { setClusterId(p.cluster_id); setPoint(p); }}><title>{p.cluster_id} · {p.team} · R{p.round_num} · CT {p.score.ct}:{p.score.t} T · {economyLabel(p.economy)}</title></circle>)}</svg>}
        <p className="muted">点击散点选择其簇与回合；左侧展示该簇的代表回合。PCA 投影并非 UMAP。</p>
        <label>键盘选择样本 <select value={point ? `${point.demo_id}:${point.round_num}:${point.team}` : ""} onChange={e => { const p = cloud.find(p => `${p.demo_id}:${p.round_num}:${p.team}` === e.target.value); if (p) { setPoint(p); setClusterId(p.cluster_id); } }}><option value="">选择回合</option>{cloud.map((p, i) => <option key={i} value={`${p.demo_id}:${p.round_num}:${p.team}`}>{p.cluster_id} · {p.team} · R{p.round_num} · {p.demo_id}</option>)}</select></label>
      </div></div>
      <p className="lab-provenance">左侧代表：{example.round.team} · R{example.round.round_num} · <code>{example.round.demo_id}</code></p>
      {round && <p>选中回合：{round.team} · R{round.round_num} · CT {round.score.ct}:{round.score.t} T · {economyLabel(round.economy)} {replays.data?.[round.demo_id]?.includes(round.round_num) ? <ReplayButton map={map} demoId={round.demo_id} round={round.round_num} /> : <span className="muted">（未导出此回合回放）</span>}</p>}
    </> : <p>暂无注意力示例。</p>}
    <aside className="lab-paper-note" role="note"><strong>论文结论（Dust2）</strong><p>{labCopy(data.metadata.paper_scope)}</p></aside>
  </section>;
}

function Shap({ data }: { data: LabData }) {
  const [roundIndex, setRoundIndex] = useState(0);
  const [timeIndex, setTimeIndex] = useState(0);
  const round = data.shap.rounds[roundIndex];
  const state = round?.states[Math.min(timeIndex, round.states.length - 1)];
  const sum = state ? Object.values(state.shap_values).reduce((s, v) => s + v, 0) : 0;
  const residual = state ? state.base_value + sum - state.t_win_prob : 0;
  return <section className="lab-panel panel" data-lab-panel="shap" aria-labelledby="lab-shap-title"><p className="eyebrow">02 / 可解释性</p><h2 id="lab-shap-title">SHAP · 分组胜率归因</h2>
    <label>示例回合 <select value={roundIndex} onChange={e => { setRoundIndex(Number(e.target.value)); setTimeIndex(0); }}>{data.shap.rounds.map((r, i) => <option key={i} value={i}>{r.map} · {r.showcase_team} R{r.round_num} · {r.demo_id}</option>)}</select></label>
    {state ? <><label className="lab-slider">冻结结束后 {state.t_s} 秒 <input type="range" aria-label="SHAP 时间轴" min="0" max={round.states.length - 1} value={Math.min(timeIndex, round.states.length - 1)} onChange={e => setTimeIndex(Number(e.target.value))} /></label>
      <p className="lab-prob">T 胜率 <strong>{fmtPct(state.t_win_prob)}</strong></p>
      <div className="shap-bars">{data.shap.groups.map(group => { const value = state.shap_values[group] ?? 0; return <div className="shap-row" key={group} data-group={group} data-value={value}><span>{GROUPS[group] ?? group}</span><div className="shap-axis"><i className={value >= 0 ? "positive" : "negative"} style={{ width: `${Math.min(.5, Math.abs(value)) * 100}%`, left: `${value >= 0 ? 50 : 50 - Math.min(.5, Math.abs(value)) * 100}%` }} /></div><strong>{signedPP(value * 100)}</strong></div>; })}</div>
      <output className="shap-additivity" data-residual={residual}>基准 {state.base_value.toFixed(6)} + Σ贡献 {sum.toFixed(6)} = {(state.base_value + sum).toFixed(6)} · 预测 {state.t_win_prob.toFixed(6)} · 残差 {residual.toExponential(2)}</output>
      <p className="muted">条形刻度：左 −50 个百分点 / 中 0 / 右 +50 个百分点；加性恒等式使用完整精度验证。观测 T 控图率 {fmtPct(state.observed_t_control)}（独立回放指标）。</p>
    </> : <p>暂无归因状态。</p>}
    <p className="lab-method"><Method value={data.shap.method} /> · 64 种组合作用 · 同图训练比赛背景 n={round?.background_n ?? data.shap.background_size} · {round?.model && <Method value={round.model} />}</p>
    <ul className="lab-limitations">{data.shap.limitations.map(limit => <li key={limit}>{labCopy(limit)}</li>)}</ul>
  </section>;
}

function Control({ data }: { data: LabData }) {
  const [phase, setPhase] = useState(0);
  const [simulate, setSimulate] = useState(false);
  const [after, setAfter] = useState(false);
  const c = data.control;
  if (!c) return <section className="lab-panel panel" data-lab-panel="control"><h2>空间控制场</h2><p>暂无控制场数据。</p></section>;
  const snapshot = c.snapshots[phase];
  const sim = c.smoke_simulation;
  const owners = simulate ? after ? sim.ownership_after : sim.ownership_before : snapshot.ownership;
  const control = simulate ? after ? sim.t_control_after : sim.t_control_before : snapshot.t_control;
  const cellWidth = Math.abs(c.cells[1]?.radar_x - c.cells[0]?.radar_x) || 40;
  const cellHeight = Math.abs(c.cells[c.grid_size]?.radar_y - c.cells[0]?.radar_y) || 40;
  return <section className="lab-panel panel" data-lab-panel="control" aria-labelledby="lab-control-title"><p className="eyebrow">03 / 空间控制</p><h2 id="lab-control-title">空间控制场 · 烟雾反事实</h2>
    <div className="lab-controls"><label>观测阶段 <select value={phase} onChange={e => { setPhase(Number(e.target.value)); setSimulate(false); }}>{c.snapshots.map((s, i) => <option key={s.phase} value={i}>{PHASES[s.phase] ?? s.phase} · {s.t_s} 秒</option>)}</select></label><button type="button" className="button" aria-pressed={simulate} onClick={() => { setSimulate(!simulate); setAfter(false); }}>💨 烟雾反事实</button>{simulate && <button type="button" className="button" aria-pressed={after} onClick={() => setAfter(!after)}>{after ? "显示投烟前" : "显示投烟后"}</button>}</div>
    <p>T 控图率 <strong>{fmtPct(control)}</strong> · {simulate ? `反事实 ${sim.t_s} 秒 · ${after ? "投烟后" : "投烟前"}` : `观测 ${snapshot.t_s} 秒`}</p>
    <svg className="lab-radar lab-control-radar" viewBox="0 0 1024 1024" role="img" aria-label="离散空间控制场" data-mode={simulate ? after ? "after" : "before" : "observed"}>
      <image href={assetUrl(`radars/${c.map}.png`)} width="1024" height="1024" />
      {c.cells.filter(cell => cell.occupied).map(cell => <rect key={cell.index} data-cell={cell.index} x={cell.radar_x - cellWidth / 2} y={cell.radar_y - cellHeight / 2} width={cellWidth} height={cellHeight} fill={owners[cell.index] === "T" ? "#ffb46b" : owners[cell.index] === "CT" ? "#75bcff" : "#8a98a5"} opacity=".55" stroke="#08151f" strokeWidth="2"><title>{owners[cell.index]} · {simulate ? "烟雾反事实" : `Δ距离 ${snapshot.delta_distance[cell.index]?.toFixed(1) ?? "—"} 世界单位`}</title></rect>)}
      {simulate && <circle cx={sim.center_radar[0]} cy={sim.center_radar[1]} r="12" fill="white"><title>烟雾中心（仅标点，非范围）</title></circle>}
    </svg>
    <p>橙色 T · 蓝色 CT · 灰色中立；未观测网格不计入控图率。</p><p className="lab-smoke-result">投烟前 {fmtPct(sim.t_control_before)} → 投烟后 {fmtPct(sim.t_control_after)} · 变化 {sim.difference_pp === null ? "—" : signedPP(sim.difference_pp)} · 路径惩罚 +{sim.penalty_units} 世界单位 · 半径 {sim.radius_units} 世界单位</p>
    <p className="lab-method">{labCopy(c.method)}。使用直线世界 XY 距离；烟雾仅为与圆盘相交的线段增加距离惩罚。无导航网格（NavMesh）、墙体或楼层建模；反事实不是实战因果预测。Δ距离 = 最近 CT 距离 − 最近 T 距离，单位不是秒。</p>
    <p className="lab-provenance">{c.map} · R{c.round_num} · <code>{c.demo_id}</code></p>
  </section>;
}

function References({ data }: { data: LabData }) {
  const [status, setStatus] = useState("");
  const accuracy = data.model_accuracy;
  const copy = async () => { try { await navigator.clipboard.writeText(data.references.map(r => `${r.authors} (${r.year}). ${r.title}. ${r.venue}. ${r.doi ? `doi:${r.doi}. ` : ""}${r.url}`).join("\n\n")); setStatus("已复制引用"); } catch { setStatus("无法访问剪贴板，请从下方选择复制。"); } };
  return <section className="lab-panel panel" data-lab-panel="references" aria-labelledby="lab-refs-title"><p className="eyebrow">04 / 验证与引用</p><h2 id="lab-refs-title">模型验证 · 学术引用</h2>
    {accuracy ? <><p>{accuracy.folds} 折按比赛留出验证 · {accuracy.matches} 场比赛 · {accuracy.rows.toLocaleString()} 个秒级状态</p><div className="lab-table-wrap"><table className="lab-metrics"><thead><tr><th>模型</th><th>准确率</th><th>对数损失</th><th>布里尔分数</th></tr></thead><tbody>{([["校准模型", accuracy.model], ["未校准模型", accuracy.model_uncalibrated], ["人数 / 时间基线", accuracy.baseline_alive_time]] as const).map(([name, m]) => <tr key={name}><th>{name}</th><td>{(m.accuracy * 100).toFixed(2)}%</td><td>{m.log_loss}</td><td>{m.brier}</td></tr>)}</tbody></table></div><p className="muted">同一回合的秒级状态相关；准确率并非独立回合预测命中率。WPA = V(sₜ₊₁) − V(sₜ)，属于模型估值差。</p></> : <p>当前导出未包含模型准确率。</p>}
    <p className="lab-method">本项目方法：<Method value={data.method} /></p><button type="button" className="button" onClick={copy}>复制学术引用</button><span role="status">{status}</span>
    <ol className="lab-references">{data.references.map(r => <li className="lab-reference" data-reference-id={r.id} key={r.id}><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a><p>{r.authors} · {r.venue} · {r.year}{r.doi ? ` · DOI: ${r.doi}` : ""}</p></li>)}</ol>
  </section>;
}

export default function AILab() {
  const { data, loading, error } = useData(getAILab, []);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorNotice error={error ?? new Error("实验室数据不可用")} />;
  return <div className="ai-lab-page"><header className="page-head"><div><p className="eyebrow">时空 AI 引擎</p><h1>🧪 AI 实验室</h1><p>从职业回合观测，到可检查的模型解释。</p><p className="muted">轻量阵型聚类 · 精确分组 Shapley · 离散空间控制</p></div></header><div className="lab-grid"><Attention data={data} /><Shap data={data} /><Control data={data} /><References data={data} /></div></div>;
}
