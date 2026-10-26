function isNum(value: number | null | undefined): value is number {
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
  return isNum(value) ? `${fmtInt(value * 100)}%` : "—";
}

export function fmtSignedNum(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return "—";
  const rounded = Number(value.toFixed(digits));
  return `${rounded >= 0 ? "+" : ""}${fmtNum(rounded, digits)}`;
}

/**
 * Percentiles on one 0–100 scale. The export writes WPA percentiles as a 0–1 share
 * ("fraction at or below") and six-axis radar percentiles as 0–100; pass the source scale,
 * or "auto" to read values above 1 as already on 0–100.
 */
export function percentile100(value: number | null | undefined, scale: "share" | "percent" | "auto" = "auto"): number | null {
  if (!isNum(value)) return null;
  const share = scale === "share" || (scale === "auto" && value <= 1);
  return Math.max(0, Math.min(100, share ? value * 100 : value));
}

/** "P74.8": the shared label for a 0–100 percentile. */
export function fmtPercentile(value: number | null | undefined): string {
  return isNum(value) ? `P${fmtNum(value, 1)}` : "—";
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
