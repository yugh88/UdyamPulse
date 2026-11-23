import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/shell/AppShell";
import { DemoGuide } from "./features/demo/DemoGuide";
import { SkeletonRows } from "./components/ui";
import { homeFor, useAuth, type Role } from "./lib/auth";

// Each screen is its own chunk so the first screen does not pay for every chart and table.
// The sign-in page is only a fallback: the prototype enters a demo persona automatically (AUTO_ENTER in lib/auth).
const Login = lazy(() => import("./pages/Login"));
const Console = lazy(() => import("./pages/Console"));
const ApplicationDetail = lazy(() => import("./pages/ApplicationDetail"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const System = lazy(() => import("./pages/System"));
const Governance = lazy(() => import("./pages/Governance"));
const MsmeApp = lazy(() => import("./pages/MsmeApp"));

const STAFF: Role[] = ["rm", "credit_officer", "risk"];
/** A screen is mounted only for roles that may use it, so it never calls an API it is not allowed to. */
const ROUTES: { path: string; page: LazyExoticComponent<ComponentType>; roles: Role[] }[] = [
  { path: "/console", page: Console, roles: ["rm", "credit_officer"] },
  { path: "/console/:id", page: ApplicationDetail, roles: STAFF },
  { path: "/alerts", page: Alerts, roles: STAFF },
  { path: "/portfolio", page: Portfolio, roles: STAFF },
  { path: "/system", page: System, roles: STAFF },
  { path: "/governance", page: Governance, roles: STAFF },
  { path: "/msme", page: MsmeApp, roles: ["msme"] },
];

function CockpitRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/alerts${search}`} replace />;
}

export default function App() {
  const { session, entering } = useAuth();
  // Opening the prototype: wait for the demo persona without touching the URL, so a shared deep link still works.
  if (entering)
    return (
      <div role="status" aria-label="Opening the demo" className="mx-auto max-w-3xl p-8">
        <p className="mb-4 text-sm text-fg-muted">Opening the demo…</p>
        <SkeletonRows rows={6} />
      </div>
    );
  return (
    <Suspense fallback={<SkeletonRows rows={6} className="mx-auto max-w-3xl p-8" />}>
      <Routes>
        <Route path="/login" element={session ? <Navigate to={homeFor(session.role)} replace /> : <Login />} />
        {session ? (
          <Route element={<AppShell />}>
            {ROUTES.filter((r) => r.roles.includes(session.role)).map((r) => (
              <Route key={r.path} path={r.path} element={<r.page />} />
            ))}
            {/* The old risk cockpit split into Alerts and Portfolio; keep its links working. */}
            <Route path="/cockpit" element={<CockpitRedirect />} />
            <Route path="*" element={<Navigate to={homeFor(session.role)} replace />} />
          </Route>
        ) : (
          <Route path="*" element={<Navigate to="/login" replace />} />
        )}
      </Routes>
      <DemoGuide />
    </Suspense>
  );
}
