import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { homeFor, useAuth } from "./lib/auth";
import ApplicationDetail from "./pages/ApplicationDetail";
import Cockpit from "./pages/Cockpit";
import Console from "./pages/Console";
import Governance from "./pages/Governance";
import Login from "./pages/Login";
import MsmeApp from "./pages/MsmeApp";

export default function App() {
  const { session } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {session ? (
        <Route element={<Layout />}>
          <Route path="/console" element={<Console />} />
          <Route path="/console/:id" element={<ApplicationDetail />} />
          <Route path="/cockpit" element={<Cockpit />} />
          <Route path="/governance" element={<Governance />} />
          <Route path="/msme" element={<MsmeApp />} />
          <Route path="*" element={<Navigate to={homeFor(session.role)} replace />} />
        </Route>
      ) : (
        <Route path="*" element={<Navigate to="/login" replace />} />
      )}
    </Routes>
  );
}
