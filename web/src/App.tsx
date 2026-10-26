import AILab from "./pages/AILab";
import About from "./pages/About";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import RoundReplay from "./components/RoundReplay";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Lineups from "./pages/Lineups";
import Players from "./pages/Players";
import { MapLinkProvider } from "./mapLink";
import Tactics from "./pages/Tactics";
import HeatmapTeams from "./pages/HeatmapTeams";
import TeamHeatmap from "./pages/TeamHeatmap";
import TeamsHub from "./pages/TeamsHub";
import { useLang } from "./i18n";

function TeamRedirect() {
  const { map = "", slug = "" } = useParams();
  return <Navigate replace to={`/teams-hub?${new URLSearchParams({ team: slug, map })}`} />;
}

export default function App() {
  useLang();
  const location = useLocation();
  const spot = new URLSearchParams(location.search).get("spot");

  return (
    <MapLinkProvider scope={`${location.pathname}:${location.search}`} initialId={spot ? `spot:${spot}` : null}><Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="lab" element={<AILab />} />
        <Route path="about" element={<About />} />
        <Route path="teams-hub" element={<TeamsHub />} />
        <Route path=":map/lineups" element={<Lineups />} />
        <Route path=":map/tactics" element={<Tactics />} />
        {/* The per-map team list was superseded by the hub; keep old links working. */}
        <Route path=":map/teams" element={<Navigate replace to="/teams-hub" />} />
        <Route path=":map/teams/:slug" element={<TeamRedirect />} />
        <Route path=":map/players" element={<Players />} />
        <Route path="heatmaps" element={<HeatmapTeams />} />
        <Route path="heatmaps/:slug" element={<TeamHeatmap />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes><RoundReplay /></MapLinkProvider>
  );
}
