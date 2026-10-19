import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Lineups from "./pages/Lineups";
import Players from "./pages/Players";
import Team from "./pages/Team";
import Teams from "./pages/Teams";
import { useLang } from "./i18n";

export default function App() {
  useLang();

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path=":map/lineups" element={<Lineups />} />
        <Route path=":map/teams" element={<Teams />} />
        <Route path=":map/teams/:slug" element={<Team />} />
        <Route path=":map/players" element={<Players />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
