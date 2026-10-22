import type { MatchDateInfo } from "./types";

export type TimeRange = "all" | "3" | "1";

export function newestMatch(a: MatchDateInfo & { demo_id: string; hltv_match_id?: number | null }, b: MatchDateInfo & { demo_id: string; hltv_match_id?: number | null }): number {
  return (b.date ?? "").localeCompare(a.date ?? "") || (b.hltv_match_id ?? 0) - (a.hltv_match_id ?? 0) || b.demo_id.localeCompare(a.demo_id);
}

/** Calendar months, clamped to the last day of the target month; UTC only. */
export function inTimeRange(match: MatchDateInfo, range: TimeRange, through?: string | null): boolean {
  if (range === "all") return true;
  if (!through || !match.date) return false;
  const [year, month, day] = through.split("-").map(Number);
  const first = new Date(Date.UTC(year, month - 1 - Number(range), 1));
  const lastDay = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  first.setUTCDate(Math.min(day, lastDay));
  return match.date >= first.toISOString().slice(0, 10) && match.date <= through;
}

export function matchDateLabel(match: MatchDateInfo): string {
  const value = match.date_precision === "event" ? match.date?.slice(0, 7) : match.date;
  return [value, match.event].filter(Boolean).join(" · ");
}
