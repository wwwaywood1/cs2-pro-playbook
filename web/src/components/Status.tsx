import { Link } from "react-router-dom";
import { DataError } from "../data";
import { t } from "../i18n";

export function Loading() {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span />
      <span />
      <span />
    </div>
  );
}

/** Localized message for a failed load; app-generated errors already carry readable text. */
export function errorMessage(error: Error): string {
  if (!(error instanceof DataError)) return error.message || t("error.unknown");
  return t(`error.${error.kind}`, { status: error.status ?? "—" });
}

/** A data failure for one page or panel: what went wrong, the file, and a way back. */
export function ErrorNotice({ error, retry = true }: { error: Error; retry?: boolean }) {
  return (
    <div className="notice notice-error" role="alert">
      <strong aria-hidden="true">! </strong>
      <span>{errorMessage(error)}</span>
      {error instanceof DataError ? <code className="notice-detail">{error.path}</code> : null}
      <span className="notice-actions">
        {retry ? <button type="button" className="button button-ghost" onClick={() => window.location.reload()}>{t("error.retry")}</button> : null}
        <Link className="button button-ghost" to="/">{t("error.back_to_maps")}</Link>
      </span>
    </div>
  );
}
