import { t, useLang } from "../i18n";
import type { PlayerProfile, Side, Wpa } from "../types";

export function signedWpa(value: number): string {
  const rounded = Math.round(value * 1000) / 10;
  return `${rounded >= 0 ? "+" : ""}${rounded.toFixed(1)}%`;
}

export function playerWpa(player: PlayerProfile | undefined, side: Side): Wpa | undefined {
  const row = player?.[side].wpa;
  return row && row.rounds > 0 && [row.per_round, row.duels].every(Number.isFinite) ? row : undefined;
}

export default function PlayerWpa({ player, side = "T" }: { player?: PlayerProfile; side?: Side }) {
  useLang();
  const wpa = playerWpa(player, side);
  if (!wpa) return null;
  const contribution = wpa.rounds_per_match ?? wpa.per_round * 24;
  const percentile = wpa.percentile;
  // Exported percentile is the fraction at or below this player, UI asks for top p%.
  const top = percentile == null ? null : Math.max(1, Math.ceil((1 - percentile) * 100));
  return <div className="player-wpa" data-side={side} data-sign={contribution >= 0 ? "positive" : "negative"}>
    <span className="stat-label">{t("round2.wpa_title")} <span className="data-tooltip" tabIndex={0} role="note" aria-label={t("round2.wpa_tip")}>ⓘ<span role="tooltip">{t("round2.wpa_tip")}</span></span></span>
    <strong className="wpa-value">{t("round2.wpa_match", { n: `${contribution >= 0 ? "+" : ""}${contribution.toFixed(2)}` })}</strong>
    <span className="wpa-rank">{top === null ? t("round2.wpa_small") : t("round2.wpa_pct", { p: top })}</span>
    <span className="stat-sub">{t("round2.wpa_duels_match", { n: `${wpa.duels >= 0 ? "+" : ""}${(wpa.duels * 24).toFixed(2)}` })}</span>
    <small>{t(`side.${side}`)} · {t("heatmap.rounds", { n: wpa.rounds })}</small>
  </div>;
}
