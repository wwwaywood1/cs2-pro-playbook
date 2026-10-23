import { t } from "../i18n";

/** Shared wording for match, round and percentile sample warnings. */
export default function LowSampleBanner({ low_sample, inline = false, compact = false }: { low_sample: boolean; inline?: boolean; compact?: boolean }) {
  if (!low_sample) return null;
  if (compact) return <span className="low-sample-chip" role="img" title={t("ui.low_sample_warning")} aria-label={t("ui.low_sample_warning")}>!</span>;
  return <span className={inline ? "low-sample-inline" : "low-sample"} role="status">
    <span className="low-sample-mark" aria-hidden="true">!</span>
    <span>{t("ui.low_sample_warning")}</span>
  </span>;
}
