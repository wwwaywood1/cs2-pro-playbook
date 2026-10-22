import { t } from "./i18n";

/** Render the exported setup tokens consistently; C joins the mid grouping. */
export function ctSetupLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const counts: Record<string, number> = {};
  for (const match of value.matchAll(/([AMBCS])(\d+)/g)) counts[match[1]] = (counts[match[1]] ?? 0) + Number(match[2]);
  if (!Object.keys(counts).length) return value;
  const label = t("round5.ct_setup_fmt", { a: counts.A ?? 0, mid: (counts.M ?? 0) + (counts.C ?? 0), b: counts.B ?? 0 });
  return counts.S ? `${label} · 出生点 ${counts.S} 人` : label;
}
