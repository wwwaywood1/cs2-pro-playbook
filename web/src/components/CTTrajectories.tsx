import type { Snapshot } from "../labTypes";

export const CT_COLORS = ["#6edcd0", "#ffc47b", "#92aaff", "#e496db", "#b1d97c"];

/** Split at floor changes; never join upper/lower Nuke points into a false path. */
export default function CTTrajectories({ snapshots, level, kind }: { snapshots: Snapshot[]; level: number; kind: "mean" | "medoid" | "sample" }) {
  return <g className={`ct-trajectories ct-${kind}`} pointerEvents="none">{Array.from({ length: 5 }, (_, slot) => {
    const segments: number[][][] = [];
    let current: number[][] = [];
    for (const frame of snapshots) {
      const p = frame.positions[slot];
      if (p && p[2] === level && Number.isFinite(p[0]) && Number.isFinite(p[1])) current.push(p);
      else { if (current.length) segments.push(current); current = []; }
    }
    if (current.length) segments.push(current);
    return <g key={slot} stroke={CT_COLORS[slot]} fill="none">{segments.map((points, index) => <g key={index}>
      <path className="ct-trajectory-path" data-kind={kind} d={points.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" ")} strokeWidth={kind === "medoid" ? 3 : 2} strokeDasharray={kind === "mean" ? "7 5" : kind === "sample" ? "2 5" : undefined} opacity={kind === "mean" ? .55 : .95} vectorEffect="non-scaling-stroke" />
      {points.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={i === points.length - 1 ? 7 : 3} fill={CT_COLORS[slot]} stroke="#08151f"><title>CT {slot + 1} · {kind}</title></circle>)}
    </g>)}</g>;
  })}</g>;
}
