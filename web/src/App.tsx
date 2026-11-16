import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/shell/AppShell";
import { SkeletonRows } from "./components/ui";
import { homeFor, useAuth } from "./lib/auth";

// Each screen is its own chunk so the login page does not pay for charts and tables.
const Login = lazy(() => import("./pages/Login"));
const Console = lazy(() => import("./pages/Console"));
const ApplicationDetail = lazy(() => import("./pages/ApplicationDetail"));
const Cockpit = lazy(() => import("./pages/Cockpit"));
const Governance = lazy(() => import("./pages/Governance"));
const MsmeApp = lazy(() => import("./pages/MsmeApp"));

export default function App() {
  const { session } = useAuth();
  return (
    <Suspense fallback={<SkeletonRows rows={6} className="mx-auto max-w-3xl p-8" />}>
      <Routes>
        <Route path="/login" element={session ? <Navigate to={homeFor(session.role)} replace /> : <Login />} />
        {session ? (
          <Route element={<AppShell />}>
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
    </Suspense>
  );
}
