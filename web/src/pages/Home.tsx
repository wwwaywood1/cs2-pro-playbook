import LowSampleBanner from "../components/LowSampleBanner";
import type { CSSProperties, ReactNode } from "react";
import { PageContext, PageSurface, MetricStrip } from "../components/Page";
import { Link } from "react-router-dom";
import { ErrorNotice, Loading } from "../components/Status";
import { getIndex, useData } from "../data";
import CountUp from "../components/CountUp";
import { ParallaxLayer, Reveal, Spotlight, Stagger } from "../components/Motion";
import { t, useLang } from "../i18n";

const MAP_CATALOG = [
  ["de_ancient", "Ancient"], ["de_anubis", "Anubis"], ["de_dust2", "Dust II"],
  ["de_inferno", "Inferno"], ["de_mirage", "Mirage"], ["de_nuke", "Nuke"], ["de_cache", "Cache"],
] as const;
function MapTile({ map, available, children, className = "", style }: { map: string; available: boolean; children: ReactNode; className?: string; style?: CSSProperties }) {
  const props = { className: `map-card ${available ? "" : "is-unavailable"} ${className}`, style, "data-motion-tilt": true };
  return <article {...props}>
    {available ? <Link className="map-card-main" to={`/${map}/tactics`}>{children}</Link> : children}
    {available ? <Link className="button button-ghost map-card-secondary" to={`/${map}/lineups`}>{t("round4.map_to_lineups")}</Link> : null}
  </article>;
}

export default function Home() {
  const lang = useLang();
  const { data, error, loading } = useData(getIndex, []);

  if (loading) return <Loading />;
  if (error || !data) {
    return <ErrorNotice error={error ?? new Error("index.json is empty")} />;
  }

  const maps = MAP_CATALOG.map(([map, display_name]) => ({ map, display_name, sample: data.maps.find((item) => item.map === map) }));

  return (
    <PageSurface className="home">
      <section className="hero" data-motion-parallax>
        <ParallaxLayer className="cover-light" />
        <p className="eyebrow">{t("site.eyebrow")}</p>
        <div className="title-hud"><h1>{t("ui.app_title")}</h1>
          <MetricStrip items={[
            { label: t("site.map_coverage"), value: data.maps.filter((item) => item.n_matches > 0).length },
            { label: t("ui.nav_lineups"), value: data.maps.reduce((n, item) => n + item.n_lineups, 0) },
          ]} />
        </div>
        <PageContext>{t("site.home_context")}</PageContext>
      </section>

      <section className="cover-maps">
        <h2 className="section-title">{t("ui.nav_maps")}</h2>
        <Stagger className="map-grid">
          {maps.map((item) => (
            <MapTile key={item.map} map={item.map} available={!!item.sample?.n_matches}>
              <img className="map-card-radar" src={`${import.meta.env.BASE_URL}radars/${item.map}.png`} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.display = "none"; }} />
              <div className="map-card-head">
                <h2>{item.display_name}</h2>
                <LowSampleBanner inline low_sample={!!item.sample && item.sample.n_matches < data.min_matches_reliable} />
              </div>
              <p className="map-code">{item.map}</p>

              {item.sample?.n_matches ? <>
                <dl className="mini-stats map-side-split">
                  <div data-side="T"><dt>{t("hub.t_win")}</dt><dd><CountUp value={item.sample.win_rate_T} format="percent" /></dd></div>
                  <div data-side="CT"><dt>{t("hub.ct_win")}</dt><dd><CountUp value={item.sample.win_rate_CT} format="percent" /></dd></div>
                </dl>
                <p className="map-top-recipe"><small>{t("tactics.recipes")}</small><strong>{item.sample.top_recipe?.name[lang] || t("tactics.no_recipes")}</strong></p>
              </> : <p className="map-no-data">{t("round4.coming_soon")}</p>}

              {item.sample?.n_matches ? <span className="map-card-cta">{t("round4.map_to_tactics")} →</span> : null}
            </MapTile>
          ))}
        </Stagger>
      </section>
      <Reveal><Spotlight className="home-entries">
        {(["teams", "tactics", "lineups"] as const).map((entry) => <Link key={entry} className="home-entry" to={entry === "teams" ? "/teams-hub" : data.maps[0] ? `/${data.maps[0].map}/${entry}` : "/"}>
          <span className="eyebrow">{t(`ui.nav_${entry}`)}</span><h2>{t(`site.${entry}_entry`)}</h2><p>{t(`site.${entry}_entry_context`)}</p><span className="entry-arrow" aria-hidden="true">↗</span>
        </Link>)}
      </Spotlight></Reveal>
    </PageSurface>
  );
}
