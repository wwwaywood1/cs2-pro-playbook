import CommandPalette from "./CommandPalette";
import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import RouteTransition from "./RouteTransition";
import { getIndex, useData } from "../data";
import { fmtDateTime } from "../format";
import { setLang, t, useLang } from "../i18n";
import { teamTheme } from "../theme";

function mapFromPath(pathname: string): string | null {
  const first = pathname.split("/").filter(Boolean)[0];
  return first?.startsWith("de_") ? first : null;
}

function navClass({ isActive }: { isActive: boolean }): string {
  return `nav-link${isActive ? " is-active" : ""}`;
}

export default function Layout() {
  const lang = useLang();
  const { pathname, search } = useLocation();
  const teamSlug = pathname === "/teams-hub" ? new URLSearchParams(search).get("team") ?? ""
    : pathname.match(/^\/[^/]+\/teams\/([^/]+)\/?$/)?.[1] ?? "";
  const { data: index } = useData(getIndex, []);
  const requestedMap = mapFromPath(pathname) ?? new URLSearchParams(search).get("map");
  const [lastMap, setLastMap] = useState<string | null>(null);
  const selectedMap = index?.maps.find((entry) => entry.map === requestedMap)?.map;
  const map = selectedMap ?? index?.maps.find((entry) => entry.map === lastMap)?.map ?? index?.maps[0]?.map;
  useEffect(() => {
    if (selectedMap) setLastMap(selectedMap);
  }, [selectedMap]);

  return (
    <div className="shell" data-team={teamSlug || undefined} style={teamSlug ? teamTheme(teamSlug) : undefined}>
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
            <NavLink to={map ? `/${map}/tactics` : "/"} className={navClass}>
              {t("ui.nav_tactics")}
            </NavLink>
            <NavLink to={map ? `/${map}/lineups` : "/"} className={navClass}>
              {t("ui.nav_lineups")}
            </NavLink>
            <NavLink to={map ? `/${map}/players` : "/"} className={navClass}>
              {t("ui.nav_players")}
            </NavLink>
            <NavLink to="/heatmaps" className={navClass}>
              {t("ui.nav_heatmaps")}
            </NavLink>
          </nav>

          <CommandPalette currentMap={map} />
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
        <RouteTransition />
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span>{t("ui.data_source_note")}</span>
          <span className="footer-data-through">{lang === "zh" ? "数据截至" : "Data through"} {index?.data_through ?? "—"}</span>
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
