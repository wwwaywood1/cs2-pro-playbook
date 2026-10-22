import { getWinprob, useData } from "../data";
import { fmtPct } from "../format";

/** Export is T-side probability, not Falcons-side probability; do not infer half/OT sides. */
export default function MatchWinprob({ map, demoId }: { map: string; demoId: string }) {
  const { data } = useData(() => getWinprob(map, demoId), [map, demoId]);
  if (!data) return null;
  const rounds = Object.entries(data.wp_t).filter(([round, values]) => Number.isFinite(Number(round))
    && Array.isArray(values) && values.length > 1 && values.every((n) => Number.isFinite(n) && n >= 0 && n <= 1))
    .sort(([a], [b]) => Number(a) - Number(b));
  if (!rounds.length) return null;
  return <details className="match-winprob">
    <summary><span>回合胜率走势 · T 方视角</span>
      <svg className="winprob-overview" viewBox="0 -2 320 44" role="img" aria-label={`本场 ${rounds.length} 回合的 T 方胜率走势，逐回合排列；展开查看每回合`}>
        <line x1="0" x2="320" y1="20" y2="20" className="winprob-midline" />
        {rounds.map(([round, values], roundIndex) => <polyline key={round} className="winprob-line"
          points={values.map((value, index) => `${((roundIndex + index / (values.length - 1) * .9) / rounds.length * 320).toFixed(1)},${(40 - value * 40).toFixed(1)}`).join(" ")} />)}
      </svg>
    </summary>
    <p className="muted">每条线为一回合：横轴按每秒采样顺序，纵轴为 T 方模型胜率 0–100%；虚线为 50%。Falcons 换边后视角仍为 T 方。</p>
    <div className="winprob-rounds">{rounds.map(([round, values]) => {
      const label = `第 ${round} 回合 · T 方胜率 ${fmtPct(values[0])} → ${fmtPct(values[values.length - 1])}`;
      const points = values.map((value, index) => `${(index / (values.length - 1) * 160).toFixed(1)},${(40 - value * 40).toFixed(1)}`).join(" ");
      return <figure key={round}>
        <figcaption>R{round}</figcaption>
        <svg viewBox="0 -2 160 44" role="img" aria-label={label}><title>{label}</title>
          <line x1="0" x2="160" y1="20" y2="20" className="winprob-midline" />
          <polyline points={points} className="winprob-line" />
        </svg>
      </figure>;
    })}</div>
  </details>;
}
