import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { getIndex, useData } from "../data";
import { fmtDateTime } from "../format";
import { setLang, t, useLang } from "../i18n";

function mapFromPath(pathname: string): string | null {
  const first = pathname.split("/").filter(Boolean)[0];
  return first?.startsWith("de_") ? first : null;
}

function navClass({ isActive }: { isActive: boolean }): string {
  return `nav-link${isActive ? " is-active" : ""}`;
}

export default function Layout() {
  const lang = useLang();
  const { pathname } = useLocation();
  const map = mapFromPath(pathname);
  const { data: index } = useData(getIndex, []);

  return (
    <div className="shell">
      <button type="button" className="skip-link" onClick={() => document.getElementById("main-content")?.focus()}>{t("ui.skip_content")}</button>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              CS
            </span>
            <span>{t("ui.app_title")}</span>
          </Link>

          <nav className="main-nav" aria-label={t("ui.primary_navigation")}>
            <NavLink to="/teams-hub" className={navClass}>
              {t("ui.nav_teams")}
            </NavLink>
            <NavLink to="/" end className={navClass}>
              {t("ui.nav_maps")}
            </NavLink>
            <NavLink to="/heatmaps" className={navClass}>
              {t("ui.nav_heatmaps")}
            </NavLink>
            {map ? (
              <>
                <NavLink to={`/${map}/lineups`} className={navClass}>
                  {t("ui.nav_lineups")}
                </NavLink>
                <NavLink to={`/${map}/tactics`} className={navClass}>
                  {t("ui.nav_tactics")}
                </NavLink>
                <NavLink to={`/${map}/players`} className={navClass}>
                  {t("ui.nav_players")}
                </NavLink>
              </>
            ) : null}
          </nav>

          <button
            type="button"
            className="lang-toggle"
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}
            aria-label={t("ui.language")}
            title={t("ui.language")}
          >
            {lang === "zh" ? "EN" : "中文"}
          </button>
        </div>
      </header>

      <main className="main" id="main-content" tabIndex={-1}>
        <Outlet />
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span>{t("ui.data_source_note")}</span>
          <span className="footer-generated">
            {t("ui.generated_at")}: {fmtDateTime(index?.generated_at, lang)}
          </span>
        </div>
        {index ? (
          <span className="footer-detail" title={index.data_source}>
            {index.data_source}
          </span>
        ) : null}
      </footer>
    </div>
  );
}
