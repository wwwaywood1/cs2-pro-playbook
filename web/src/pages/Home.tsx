import { Link } from "react-router-dom";
import { ErrorNotice, Loading } from "../components/Status";
import { getIndex, useData } from "../data";
import { fmtInt } from "../format";
import { t, useLang } from "../i18n";

export default function Home() {
  useLang();
  const { data, error, loading } = useData(getIndex, []);

  if (loading) return <Loading />;
  if (error || !data) {
    return <ErrorNotice error={error ?? new Error("index.json is empty")} />;
  }

  return (
    <div className="home">
      <section className="hero">
        <h1>{t("ui.app_title")}</h1>
        <p className="hero-copy">{t("ui.data_source_note")}</p>
      </section>

      <section>
        <h2 className="section-title">{t("ui.nav_maps")}</h2>
        <div className="map-grid">
          {data.maps.map((item) => (
            <Link key={item.map} to={`/${item.map}/lineups`} className="map-card">
              <div className="map-card-head">
                <h2>{item.display_name}</h2>
                {item.n_matches < data.min_matches_reliable ? (
                  <span
                    className="tag-warn"
                    title={t("ui.low_sample_warning", { n: item.n_matches })}
                    aria-label={t("ui.low_sample_warning", { n: item.n_matches })}
                  >
                    !
                  </span>
                ) : null}
              </div>
              <p className="map-code">{item.map}</p>

              <dl className="mini-stats">
                <div>
                  <dt>{t("ui.matches_title")}</dt>
                  <dd>{fmtInt(item.n_matches)}</dd>
                </div>
                <div>
                  <dt>{t("ui.nav_lineups")}</dt>
                  <dd>{fmtInt(item.n_lineups)}</dd>
                </div>
                <div>
                  <dt>{t("ui.nav_players")}</dt>
                  <dd>{fmtInt(item.n_players)}</dd>
                </div>
              </dl>

              <span className="map-card-cta">
                {t("ui.nav_lineups")} →
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
