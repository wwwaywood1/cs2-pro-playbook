import { useState } from "react";
import { fmtNum } from "../format";
import { useLang } from "../i18n";
import type { PlayerProfile, Radar6Axis, Side } from "../types";
import "../radar6.css";

const AXES: [Radar6Axis, string, string, string, string][] = [
  ["entry", "首杀参与", "Entry", "取得首杀或首死的回合占比。", "Share of rounds with the opening kill or death."],
  ["trade", "补枪", "Trade", "4 秒内自身死亡被补与补队友死亡的占比均值。", "Mean of own deaths traded and teammate deaths traded within 4 seconds."],
  ["lurk_distance", "游走距离", "Lurk distance", "15 秒后下包前，与存活队友中心的平均曼哈顿距离；仅 T。", "Mean Manhattan distance to alive teammates after 15 seconds, before plant; T only."],
  ["space_gain", "空间推进", "Space gain", "每回合存活期间朝敌方出生点净推进的距离。", "Net advance toward enemy spawn while alive, per round."],
  ["utility_impact", "道具影响", "Utility", "每回合闪光助攻与燃烧弹半径内位移超 150 单位的敌人数。", "Flash assists plus sampled enemy fire displacements, per round."],
  ["clutch_wpa", "残局贡献", "Clutch WPA", "首次 1vN 时，胜负减去当时模型胜率的均值。", "Mean outcome minus held-out WP at the first 1vN state."],
];
const point = (axis: number, radius: number): [number, number] => {
  const angle = axis * Math.PI / 3 - Math.PI / 2;
  return [150 + Math.cos(angle) * radius, 130 + Math.sin(angle) * radius];
};

export default function PlayerRadar6({ player, side }: { player?: PlayerProfile; side: Side }) {
  const lang = useLang();
  const [active, setActive] = useState<number | null>(null);
  const profile = player?.[side].radar_6d;
  if (!profile) return null;
  const title = lang === "zh" ? "六维风格" : "Six-axis profile";
  const percentiles = AXES.map(([key]) => profile[key].percentile);
  const points = percentiles.map((value, i) => value == null ? null : point(i, value * .82));
  const tooltip = (i: number) => {
    const [key, zh, en, zhHelp, enHelp] = AXES[i];
    const metric = profile[key];
    return `${lang === "zh" ? zh : en} · ${metric.percentile == null ? "—" : `P${fmtNum(metric.percentile, 1)}`} · ${lang === "zh" ? "原值" : "Raw"} ${fmtNum(metric.raw, 3)} · ${lang === "zh" ? zhHelp : enHelp}`;
  };
  return <figure className="player-radar6" data-side={side}>
    <figcaption>{title} · {side}<small>{lang === "zh" ? "同图同阵营百分位 · ≥50 回合" : "Map / side percentiles · ≥50 rounds"}</small></figcaption>
    <svg viewBox="0 0 300 260" role="group" aria-label={`${title} · ${side}`}>
      {[.25, .5, .75, 1].map((fraction) => <polygon key={fraction} points={AXES.map((_, i) => point(i, 82 * fraction).join(",")).join(" ")} className="radar6-ring" />)}
      {AXES.map(([key], i) => <line key={key} x1="150" y1="130" x2={point(i, 82)[0]} y2={point(i, 82)[1]} className="radar6-axis" />)}
      {points.every((p) => p !== null) ? <polygon className="radar6-area" points={points.map((p) => p!.join(",")).join(" ")} /> : points.map((p, i) => {
        const next = points[(i + 1) % 6];
        return p && next ? <line key={i} className="radar6-edge" x1={p[0]} y1={p[1]} x2={next[0]} y2={next[1]} /> : null;
      })}
      {AXES.map(([key, zh, en], i) => {
        const label = point(i, 108);
        const p = points[i];
        return <g key={key} tabIndex={0} role="img" aria-label={tooltip(i)} data-axis={key} onPointerEnter={() => setActive(i)} onPointerLeave={() => setActive(null)} onFocus={() => setActive(i)} onBlur={() => setActive(null)}>
          <title>{tooltip(i)}</title>
          <circle cx={point(i, 82)[0]} cy={point(i, 82)[1]} r="14" fill="transparent" />
          {p ? <circle cx={p[0]} cy={p[1]} r="3" className="radar6-dot" /> : null}
          <text x={label[0]} y={label[1]} textAnchor="middle" dominantBaseline="middle" className={p ? "" : "radar6-missing"}>{lang === "zh" ? zh : en}{p ? "" : " —"}</text>
        </g>;
      })}
    </svg>
    <p className="radar6-tooltip" role="status">{active == null ? (profile.eligible ? (lang === "zh" ? "悬停查看百分位与定义；数值描述风格。" : "Hover for percentiles and definitions; axes describe style.") : (lang === "zh" ? "本侧不足 50 回合，保留原值，暂无百分位。" : "Fewer than 50 side rounds; raw values only.")) : tooltip(active)}</p>
  </figure>;
}
