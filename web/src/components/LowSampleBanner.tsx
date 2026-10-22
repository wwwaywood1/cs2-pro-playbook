import { t } from "../i18n";

/** Shared wording for match, round and percentile sample warnings. */
export default function LowSampleBanner({ low_sample, inline = false }: { low_sample: boolean; inline?: boolean }) {
  if (!low_sample) return null;
  return <span className={inline ? "low-sample-inline" : "low-sample"} role="status">
    <span className="low-sample-mark" aria-hidden="true">!</span>
    <span>{t("ui.low_sample_warning")}</span>
  </span>;
}
