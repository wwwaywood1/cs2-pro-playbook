import { Component, type ErrorInfo, type ReactNode } from "react";
import { clearDataCache } from "../data";
import { t } from "../i18n";

interface Props {
  children: ReactNode;
  /** A new key (route, round) clears a caught error so the next view renders normally. */
  resetKey?: string;
  /** Replaces the default page-level message, e.g. inside the replay dialog. */
  fallback?: (error: Error, retry: () => void) => ReactNode;
}

/**
 * Contains a render failure, typically an export whose JSON lacks a field the page reads,
 * to the region it wraps: the nav, footer and other dialogs keep working. Retry drops
 * the cached requests so that a fixed or redeployed file is fetched again.
 */
export default class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error : new Error(String(error)) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error contained by ErrorBoundary:", error, info.componentStack);
  }

  componentDidUpdate(previous: Props) {
    if (this.state.error && previous.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  retry = () => {
    clearDataCache();
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.retry);
    return <div className="notice notice-error route-error" role="alert">
      <strong>{t("error.render_title")}</strong>
      <span>{t("error.render")}</span>
      <span className="notice-actions">
        <button type="button" className="button button-ghost" onClick={this.retry}>{t("error.retry")}</button>
        {/* A plain link: the router may be the part that failed. */}
        <a className="button button-ghost" href="#/">{t("error.back_to_maps")}</a>
      </span>
    </div>;
  }
}
