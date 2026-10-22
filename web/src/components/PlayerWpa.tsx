import type { PlayerProfile, Side, Wpa } from "../types";

export const WPA_HELP = "从选手所在队伍视角，统计事件前最后一整秒到事件后 2 秒的模型胜率变化，再除以该侧回合数。交火包含击杀与死亡，道具在爆开时记给投掷者；不含下包。道具作用可能延迟，估计较小且有噪声；这是关联估计，不是因果贡献。总览按 T / CT 的样本回合数加权。百分数表示胜率百分点。";

export function signedWpa(value: number): string {
  const rounded = Math.round(value * 1000) / 10;
  return `${rounded >= 0 ? "+" : ""}${rounded.toFixed(1)}%`;
}

/** Never silently treat a missing side's export as zero contribution. */
export function playerWpa(player: PlayerProfile | undefined, side: Side | "all"): Wpa | undefined {
  if (!player) return undefined;
  const sides: Side[] = side === "all" ? ["T", "CT"] : [side];
  const rows = sides.map((s) => player[s].wpa);
  if (rows.some((row) => !row || !Number.isFinite(row.rounds) || row.rounds <= 0
    || ![row.per_round, row.duels, row.utility].every(Number.isFinite))) return undefined;
  const valid = rows as Wpa[];
  const rounds = valid.reduce((sum, row) => sum + row.rounds, 0);
  const rate = (key: "per_round" | "duels" | "utility") => valid.reduce((sum, row) => sum + row[key] * row.rounds, 0) / rounds;
  return { rounds, per_round: rate("per_round"), duels: rate("duels"), utility: rate("utility") };
}

export default function PlayerWpa({ player, side = "all" }: { player?: PlayerProfile; side?: Side | "all" }) {
  const wpa = playerWpa(player, side);
  if (!wpa) return null;
  return <div className="player-wpa">
    <span className="stat-label">每回合胜率贡献 <span className="data-tooltip" tabIndex={0} role="note" aria-label={WPA_HELP}>ⓘ<span role="tooltip">{WPA_HELP}</span></span></span>
    <strong className="wpa-value">{signedWpa(wpa.per_round)}</strong>
    <span className="stat-sub">交火 {signedWpa(wpa.duels)} · 道具 {signedWpa(wpa.utility)}</span>
    <small>{side === "all" ? "T / CT 加权" : `${side} 方`} · {wpa.rounds} 回合</small>
  </div>;
}
