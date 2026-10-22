import { getWinprob, useData } from "../data";
import { t, useLang } from "../i18n";

/** Side metadata comes from team_rounds, so half changes and OT stay team-relative. */
export default function MatchWinprob({ map, demoId, teamSlug }: { map: string; demoId: string; teamSlug: string }) {
  useLang();
  const { data } = useData(() => getWinprob(map, demoId), [map, demoId]);
  const sides = data?.team_sides?.[teamSlug];
  if (!data || !sides) return null;
  const rounds = Object.entries(data.wp_t).filter(([round, values]) => Number.isFinite(Number(round))
    && (sides[round] === "T" || sides[round] === "CT")
    && Array.isArray(values) && values.length > 1 && values.every((n) => Number.isFinite(n) && n >= 0 && n <= 1))
    .sort(([a], [b]) => Number(a) - Number(b));
  if (!rounds.length) return null;
  const width = rounds.length * 16;
  const half = rounds.findIndex(([round]) => Number(round) > 12);
  return <figure className="match-winprob">
    <figcaption>{t("round2.round_bar_title")}</figcaption>
    <svg className="winprob-overview" viewBox={`0 0 ${width} 108`} role="group" aria-label={t("round2.round_bar_title")}>
      <line x1="0" x2={width} y1="50" y2="50" className="winprob-midline" />
      {rounds.map(([round, values], index) => {
        const from = sides[round] === "T" ? values[0] : 1 - values[0];
        const to = sides[round] === "T" ? values[values.length - 1] : 1 - values[values.length - 1];
        const delta = to - from;
        const height = Math.abs(delta) * 45;
        const label = t("round2.round_bar_tip", { r: round, from: Math.round(from * 100), to: Math.round(to * 100) });
        return <g key={round} className="winprob-round" tabIndex={0} role="img" aria-label={label}>
          <title>{label}</title>
          <rect x={index * 16 + 2} y={delta >= 0 ? 50 - height : 50} width="12" height={height || .5} className={`winprob-bar ${delta >= 0 ? "is-positive" : "is-negative"}`} />
          <rect x={index * 16} y="0" width="16" height="98" fill="transparent" />
          <text x={index * 16 + 8} y="106" textAnchor="middle">{round}</text>
        </g>;
      })}
      {half > 0 ? <line x1={half * 16} x2={half * 16} y1="0" y2="98" className="winprob-halftime" /> : null}
    </svg>
  </figure>;
}
