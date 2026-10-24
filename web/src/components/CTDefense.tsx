import { useState } from "react";
import { getAILab, getCTPatterns, getReplay, getReplayIndex, useData } from "../data";
import { fmtPct } from "../format";
import type { Snapshot } from "../labTypes";
import RecipeRadar from "./RecipeRadar";
import CTTrajectories from "./CTTrajectories";
import { ErrorNotice, Loading } from "./Status";
import "../lab.css";

const CONTEXT: Record<string, string> = { full: "全起", force: "强起", eco: "经济局", pistol: "手枪局", trailing: "比分落后", leading: "比分领先", tied: "比分持平", after_loss: "上回合失利" };
export const signedPP = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(1)} pp`;

export default function CTDefense({ map }: { map: string }) {
  const { data, loading, error } = useData(() => getCTPatterns(map), [map]);
  const lab = useData(getAILab, []);
  const replays = useData(() => getReplayIndex(map), [map]);
  const [chosen, setChosen] = useState("");
  const [sampleKey, setSampleKey] = useState("");
  const cluster = data?.clusters.find(c => c.id === chosen) ?? data?.clusters[0];
  const medoid = lab.data?.attention.find(a => a.map === map && a.cluster_id === cluster?.id);
  const samples = (data?.embedding.points ?? []).filter(p => p.cluster_id === cluster?.id && replays.data?.[p.demo_id]?.includes(p.round_num)).slice(0, 12);
  const sample = samples.find(p => `${p.demo_id}:${p.round_num}` === sampleKey) ?? samples[0];
  const replay = useData(() => sample ? getReplay(map, sample.demo_id, sample.round_num) : Promise.resolve(null), [map, sample?.demo_id, sample?.round_num]);
  const sampleReplay = replay.data?.demo_id === sample?.demo_id && replay.data?.round_num === sample?.round_num ? replay.data : null;
  const sampleSnapshots: Snapshot[] = sampleReplay ? [10, 12, 15, 18, 20].map(t_s => ({ t_s, positions: sampleReplay.players.flatMap((p, i) => p.side === "CT" ? [sampleReplay.frames[t_s]?.[i] ? [...sampleReplay.frames[t_s][i]!, 0] : []] : []) })) : [];
  if (loading) return <Loading />;
  if (error || !data) return <ErrorNotice error={error ?? new Error("暂无 CT 阵型数据")} />;
  if (!cluster) return <p className="notice">暂无完整 CT 阵型样本。</p>;
  const levels = [...new Set([...cluster.trajectories, ...(medoid?.snapshots ?? [])].flatMap(s => s.positions.map(p => p[2])))];
  const chi = data.chi_square;
  return <section className="ct-defense" data-map={map} aria-label="CT 防守阵型">
    <header><h2>CT 防守 · 动态阵型</h2><p>{data.counts.included.toLocaleString()} 个完整 CT 回合 · {data.clusters.length} 簇 · 已排除 {data.counts.dropped_outlier} 个离群回合</p></header>
    {map === "de_overpass" && <p className="lab-warning">历史地图 Overpass · 仅因你明确选择此地图而显示。</p>}
    <p className="lab-method">方法：{data.method} · {data.metadata.clustering_note}</p>
    <div className="ct-workspace tactics-workspace">
      <aside className="tactics-map-panel">
        <RecipeRadar map={map} spots={[]} scale={undefined} title={cluster.label_zh} selectionLabel="冻结结束后 10 / 12 / 15 / 18 / 20 秒" overlayLevels={levels} routeKey={cluster.id}
          overlay={level => <><CTTrajectories snapshots={cluster.trajectories} level={level} kind="mean" /><CTTrajectories snapshots={medoid?.snapshots ?? []} level={level} kind="medoid" />{map !== "de_nuke" && <CTTrajectories snapshots={sampleSnapshots} level={level} kind="sample" />}</>} />
        <p className="muted">虚线：簇均值 · 实线：代表回合（medoid）· 点线：可用回放样本。颜色标识固定队员槽位，各回合间不对应同一选手。</p>
        <p className="lab-provenance">代表：{cluster.medoid.team} · R{cluster.medoid.round_num} · CT {cluster.medoid.score.ct}:{cluster.medoid.score.t} T · {cluster.medoid.economy}<br /><code>{cluster.medoid.demo_id}</code></p>
        {lab.loading ? <p role="status">正在加载代表回合轨迹…</p> : lab.error || !medoid ? <p role="status">代表回合轨迹暂不可用；当前显示簇均值。</p> : null}
        {map === "de_nuke" ? <p className="muted">Nuke 代表/均值轨迹按楼层分段；回放格式缺少楼层信息，不叠加回放样本。</p> : samples.length ? <label>回放样本 <select value={sample ? `${sample.demo_id}:${sample.round_num}` : ""} onChange={e => setSampleKey(e.target.value)}>{samples.map(p => <option key={`${p.demo_id}:${p.round_num}`} value={`${p.demo_id}:${p.round_num}`}>{p.team} · R{p.round_num} · {p.demo_id}</option>)}</select></label> : <p className="muted">此簇暂无可用的回放样本；保留真实代表回合与簇均值。</p>}
        {replay.error && <p role="status">回放样本加载失败。</p>}
        <p className="lab-method">后续死亡队员保留导出记录位置；线条连接采样时刻，不推断中间移动或穿墙路径。</p>
      </aside>
      <div className="ct-cluster-list">{data.clusters.map(c => <button type="button" key={c.id} className={`ct-cluster-card panel${c.id === cluster.id ? " is-selected" : ""}`} aria-pressed={c.id === cluster.id} data-cluster-id={c.id} data-share={c.share} onClick={() => { setChosen(c.id); setSampleKey(""); }}>
        <strong>{c.id} · {c.label_zh}</strong><span>占比 {fmtPct(c.share)} · n = {c.n}</span><span>CT 胜率 {fmtPct(c.ct_win_rate)} · 95% CI [{fmtPct(c.ct_win_ci95[0])}, {fmtPct(c.ct_win_ci95[1])}]</span>
        {c.n < data.metadata.min_cluster_size && <span className="lab-warning">样本不足（最低 {data.metadata.min_cluster_size} 回合），结果仅供参考。</span>}
        <span className="ct-context">{Object.entries(c.context_preferences).map(([key, p]) => <span key={key}>{CONTEXT[key] ?? key} {fmtPct(p.share)} <small>相对全图 {p.difference_pp === null ? "—" : signedPP(p.difference_pp)} · n={p.n}</small></span>)}</span>
      </button>)}</div>
    </div>
    <div className="panel ct-chi"><h3>经济类型 × 阵型 · χ² 检验</h3><p>χ² = {chi.statistic.toFixed(2)} · df = {chi.dof} · p = {chi.p.toExponential(3)} · 最小期望频数 {chi.min_expected?.toFixed(2) ?? "—"}</p>
      {(chi.caveat || (chi.min_expected !== null && chi.min_expected < 5)) && <p className="lab-warning">稀疏单元格警告：{chi.caveat ?? "部分期望频数低于 5；渐近检验需谨慎解释。"}</p>}
      <p className="muted">情境偏好为簇内情境占比减去全图情境占比；相关性不代表因果。</p></div>
  </section>;
}
