import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Lineups from "./pages/Lineups";
import Players from "./pages/Players";
import Team from "./pages/Team";
import Teams from "./pages/Teams";
import Tactics from "./pages/Tactics";
import HeatmapTeams from "./pages/HeatmapTeams";
import TeamHeatmap from "./pages/TeamHeatmap";
import TeamsHub from "./pages/TeamsHub";
import { useLang } from "./i18n";

export default function App() {
  useLang();

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="teams-hub" element={<TeamsHub />} />
        <Route path=":map/lineups" element={<Lineups />} />
        <Route path=":map/tactics" element={<Tactics />} />
        <Route path=":map/teams" element={<Teams />} />
        <Route path=":map/teams/:slug" element={<Team />} />
        <Route path=":map/players" element={<Players />} />
        <Route path="heatmaps" element={<HeatmapTeams />} />
        <Route path="heatmaps/:slug" element={<TeamHeatmap />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
