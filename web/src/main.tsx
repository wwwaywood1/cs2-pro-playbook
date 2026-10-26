import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { t } from "./i18n";
import "./styles.css";
import "./hud.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

// Pages and the replay dialog have their own boundaries; this one only catches a
// failure in the shell itself, which would otherwise leave a blank document.
createRoot(root).render(
  <StrictMode>
    <ErrorBoundary fallback={() => <div className="notice notice-error app-error" role="alert">
      <strong>{t("error.app")}</strong>
      <button type="button" className="button" onClick={() => window.location.reload()}>{t("error.reload")}</button>
    </div>}>
      <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </HashRouter>
    </ErrorBoundary>
  </StrictMode>,
);
