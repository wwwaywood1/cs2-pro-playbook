export function isNum(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function fmtInt(value: number | null | undefined): string {
  if (!isNum(value)) return "—";
  return Math.round(value).toLocaleString("en-US");
}

export function fmtNum(value: number | null | undefined, digits = 2): string {
  return isNum(value) ? value.toFixed(digits) : "—";
}

export function fmtPct(value: number | null | undefined): string {
  return isNum(value) ? `${Math.round(value * 100)}%` : "—";
}

export function fmtSeconds(value: number | null | undefined, digits = 1): string {
  return isNum(value) ? `${value.toFixed(digits)}s` : "—";
}

const RATE_METRICS = new Set([
  "hs_pct",
  "opening_success",
  "traded_death_rate",
  "awp_share",
  "win_rate",
  "opening_win_rate",
  "retake_win_rate",
  "stack_rate_15s",
  "round_win_rate",
  "ct_lane_15s_share",
  "first_into_site_rate",
  "t_first_into_site_rate",
]);

/** Format a metric value for a role hint, using the unit that metric reports in. */
export function fmtMetric(metric: string, value: number | null | undefined): string {
  if (!isNum(value)) return "—";
  if (metric.includes("dist_to_team")) return fmtInt(value);
  if (RATE_METRICS.has(metric)) return fmtPct(value);
  return fmtNum(value, 2);
}

export function fmtDateTime(iso: string | null | undefined, lang: "zh" | "en"): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === "zh" ? "zh-CN" : "en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
