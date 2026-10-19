import { t } from "../i18n";

interface Props {
  n_matches: number;
  low_sample: boolean;
}

export default function LowSampleBanner({ n_matches, low_sample }: Props) {
  if (!low_sample) return null;
  return (
    <div className="low-sample" role="status">
      <span className="low-sample-mark" aria-hidden="true">
        !
      </span>
      <span>{t("ui.low_sample_warning", { n: n_matches })}</span>
    </div>
  );
}
