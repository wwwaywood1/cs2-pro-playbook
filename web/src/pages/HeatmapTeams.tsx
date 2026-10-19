import { Link, useSearchParams } from "react-router-dom";
import { ErrorNotice, Loading } from "../components/Status";
import { getHeatmapTeams, useData } from "../data";
import { playerColor } from "../heatmap";
import { t, useLang } from "../i18n";
import "../heatmap.css";

export default function HeatmapTeams() {
  useLang();
  const { data: teams, error, loading } = useData(getHeatmapTeams, []);
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const filtered = (teams ?? []).filter((team) => team.team.toLowerCase().includes(search.trim().toLowerCase()));
  return (
    <div className="hm-page">
      <header className="page-head">
        <div><h1>{t("heatmap.title")}</h1><p>{t("heatmap.pick_team")}</p></div>
      </header>
      <label className="hm-search">
        <span>{t("heatmap.search")}</span>
        <input type="search" value={search} placeholder={t("heatmap.search")} onChange={(event) => {
          const next = new URLSearchParams(params);
          if (event.target.value) next.set("q", event.target.value);
          else next.delete("q");
          setParams(next, { replace: true });
        }} />
      </label>
      {loading ? <Loading /> : error ? <ErrorNotice error={error} /> : filtered.length === 0 ? (
        <p>{t("heatmap.no_data")}</p>
      ) : (
        <div className="hm-team-grid">
          {filtered.map((team) => (
            <Link key={team.slug} to={`/heatmaps/${encodeURIComponent(team.slug)}`} className="hm-team-card">
              <h2>{team.team}</h2>
              <p>{t("heatmap.matches")} · {team.n_matches ?? "—"} · {t("heatmap.maps_count")} · {team.maps.length}</p>
              <ul>
                {team.roster.filter((player) => player.color < 5).sort((a, b) => a.color - b.color).slice(0, 5).map((player) => (
                  <li key={player.steamid}>
                    <span className="hm-swatch" style={{ backgroundColor: playerColor(player.color).deep }} aria-hidden="true" />
                    {player.name}
                  </li>
                ))}
              </ul>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
