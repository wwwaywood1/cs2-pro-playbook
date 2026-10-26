import { fmtInt, fmtPct, fmtPercentile, fmtSignedNum, percentile100 } from "../format";
import LowSampleBanner from "./LowSampleBanner";
import { t, useLang } from "../i18n";
import type { PlayerProfile, Side, Wpa } from "../types";

function playerWpa(player: PlayerProfile | undefined, side: Side): Wpa | undefined {
  const row = player?.[side].wpa;
  return row && row.rounds > 0 && [row.per_round, row.duels].every(Number.isFinite) ? row : undefined;
}

export default function PlayerWpa({ player, side = "T" }: { player?: PlayerProfile; side?: Side }) {
  const lang = useLang();
  const wpa = playerWpa(player, side);
  if (!wpa) return null;
  const contribution = wpa.rounds_per_match ?? wpa.per_round * 24;
  // Exported as the share of players at or below this value (0–1); the six-axis radar
  // uses 0–100. Both are shown on the 0–100 scale; the headline asks for "top p%".
  const percentile = percentile100(wpa.percentile);
  const top = percentile == null ? null : Math.max(1, Math.ceil(100 - percentile));
  const tip = `${t("round2.wpa_tip")} ${t("round2.wpa_drift_note")}${lang === "zh" ? "。" : "."}`;
  return <div className="player-wpa" data-side={side} data-sign={contribution >= 0 ? "positive" : "negative"} data-percentile={percentile ?? undefined}>
    <span className="stat-label">{t("round2.wpa_title")} <span className="data-tooltip" tabIndex={0} role="note" aria-label={tip}>ⓘ<span role="tooltip">{tip}</span></span></span>
    <strong className="wpa-value">{t("round2.wpa_match", { n: fmtSignedNum(contribution) })}<sup className="wpa-note-mark" aria-hidden="true">*</sup></strong>
    {top === null ? <LowSampleBanner low_sample inline /> : <span className="wpa-rank">{t("round2.wpa_pct", { p: fmtPct(top / 100) })} · {fmtPercentile(percentile)}</span>}
    <span className="stat-sub">{t("round2.wpa_duels_match", { n: fmtSignedNum(wpa.duels * 24) })}</span>
    <small>{t(`side.${side}`)} · {t("heatmap.rounds", { n: fmtInt(wpa.rounds) })}</small>
    <small className="wpa-note">* {t("round2.wpa_drift_note")}</small>
  </div>;
}
