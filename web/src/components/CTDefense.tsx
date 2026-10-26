import { useState } from "react";
import { getAILab, getCTPatterns, useData } from "../data";
import { fmtPct } from "../format";
import { useLang } from "../i18n";
import { economyLabel, labCopy, methodName } from "../labCopy";
import RecipeRadar from "./RecipeRadar";
import CTTrajectories from "./CTTrajectories";
import { ErrorNotice, Loading } from "./Status";
import "../lab.css";

export const signedPP = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(1)} pp`;

export default function CTDefense({ map }: { map: string }) {
  const lang = useLang();
  const { data, loading, error } = useData(() => getCTPatterns(map), [map]);
  const lab = useData(getAILab, []);
  const [chosen, setChosen] = useState("");
  const [showMean, setShowMean] = useState(false);
  const cluster = data?.clusters.find(c => c.id === chosen) ?? data?.clusters[0];
  const medoid = lab.data?.attention.find(a => a.map === map && a.cluster_id === cluster?.id);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorNotice error={error ?? new Error("暂无 CT 阵型数据")} />;
  if (!cluster) return <p className="notice">暂无完整 CT 阵型样本。</p>;
  const levels = [...new Set([...cluster.trajectories, ...(medoid?.snapshots ?? [])].flatMap(s => s.positions.map(p => p[2])))];
  const chi = data.chi_square;
  const observed = chi.observed ?? [];
  const n = observed.flat().reduce((sum, value) => sum + value, 0);
  const dimension = Math.min(observed.length - 1, (observed[0]?.length ?? 0) - 1);
  const effectSize = chi.cramers_v ?? (n > 0 && dimension > 0 ? Math.sqrt(chi.statistic / (n * dimension)) : null);
  return <section className="ct-defense" data-map={map} aria-label="CT 防守阵型">
    <header><h2>CT 防守 · 动态阵型</h2><p>{data.counts.included.toLocaleString()} 个完整 CT 回合 · {data.clusters.length} 簇 · 已排除 {data.counts.dropped_outlier} 个离群回合</p>{data.metadata.excluded_pistol_rounds != null && <p className="ct-pistol-note">已排除手枪局 {data.metadata.excluded_pistol_rounds.toLocaleString()} 回合</p>}</header>
    {map === "de_overpass" && <p className="lab-warning">历史地图 Overpass · 仅因你明确选择此地图而显示。</p>}
    <p className="lab-method">方法：{methodName(data.method, lang)} · {labCopy(data.metadata.clustering_note, lang)}</p>
    <div className="ct-workspace tactics-workspace">
      <aside className="tactics-map-panel">
        <label className="ct-mean-toggle"><input type="checkbox" checked={showMean} onChange={e => setShowMean(e.target.checked)} />叠加簇均值轨迹</label>
        <RecipeRadar map={map} spots={[]} scale={undefined} title={cluster.label_zh} selectionLabel="冻结结束后 10 s 起点 / 20 s 终点" overlayLevels={levels} routeKey={cluster.id}
          overlay={level => <>{showMean && <CTTrajectories snapshots={cluster.trajectories} level={level} kind="mean" />}<CTTrajectories snapshots={medoid?.snapshots ?? []} level={level} kind="medoid" /></>} />
        <p className="muted">实线：代表回合（medoid）· 小圆点：10 s 起点 · 大圆点：20 s 终点；勾选后虚线：簇均值。颜色标识固定队员槽位，各回合间不对应同一选手。</p>
        <p className="lab-provenance">代表：{cluster.medoid.team} · R{cluster.medoid.round_num} · CT {cluster.medoid.score.ct}:{cluster.medoid.score.t} T · {economyLabel(cluster.medoid.economy)}<br /><code>{cluster.medoid.demo_id}</code></p>
        {lab.loading ? <p role="status">正在加载代表回合轨迹…</p> : lab.error || !medoid ? <p role="status">代表回合轨迹暂不可用；可勾选叠加簇均值轨迹。</p> : null}
        <p className="lab-method">后续死亡队员保留导出记录位置；线条连接采样时刻，不推断中间移动或穿墙路径。</p>
      </aside>
      <div className="ct-cluster-list">{data.clusters.map(c => <button type="button" key={c.id} className={`ct-cluster-card panel${c.id === cluster.id ? " is-selected" : ""}`} aria-pressed={c.id === cluster.id} data-cluster-id={c.id} data-share={c.share} onClick={() => { setChosen(c.id); }}>
        <strong>{c.id} · {c.label_zh}</strong><span>占比 {fmtPct(c.share)} · n = {c.n}</span><span>CT 胜率 {fmtPct(c.ct_win_rate)} · 95% CI [{fmtPct(c.ct_win_ci95[0])}, {fmtPct(c.ct_win_ci95[1])}]</span>
        {c.n < data.metadata.min_cluster_size && <span className="lab-warning">样本不足（最低 {data.metadata.min_cluster_size} 回合），结果仅供参考。</span>}
        <span className="ct-context">{Object.entries(c.context_preferences).map(([key, p]) => <span key={key}>{economyLabel(key)} {fmtPct(p.share)} <small>相对全图 {p.difference_pp === null ? "—" : signedPP(p.difference_pp)} · n={p.n}</small></span>)}</span>
      </button>)}</div>
    </div>
    <div className="panel ct-chi"><h3>经济类型 × 阵型 · χ² 检验</h3><p>χ² = {chi.statistic.toFixed(2)} · df = {chi.dof} · {chi.p_display ?? (chi.p < 1e-4 ? "p < 0.0001" : `p = ${chi.p.toPrecision(4)}`)}{effectSize != null && Number.isFinite(effectSize) ? ` · Cramér's V = ${effectSize.toFixed(2)}` : ""} · 最小期望频数 {chi.min_expected?.toFixed(2) ?? "—"}</p>
      {(chi.caveat || (chi.min_expected !== null && chi.min_expected < 5)) && <p className="lab-warning">稀疏单元格警告：{chi.caveat ? labCopy(chi.caveat, lang) : "部分期望频数低于 5；渐近检验需谨慎解释。"}</p>}
      <p className="muted">情境偏好为簇内情境占比减去全图情境占比；相关性不代表因果。</p></div>
  </section>;
}
