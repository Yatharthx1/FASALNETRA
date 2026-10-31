import { lazy, Suspense } from "react";
import { ErrorBoundary, Skeleton } from "./components/common";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Walk = lazy(() => import("./pages/Walk"));
const Didi = lazy(() => import("./pages/Didi"));

// Three surfaces, no router library needed: the SMS link opens /walk, Drone Didi uses /didi, judges see /.
const ROUTES: Record<string, React.ComponentType> = { "/walk": Walk, "/didi": Didi };

export default function App() {
  const Page = ROUTES[location.pathname.replace(/\/$/, "")] ?? Dashboard;
  return (
    <ErrorBoundary>
      <Suspense fallback={<main className="walk"><Skeleton height={320} /></main>}>
        <Page />
      </Suspense>
    </ErrorBoundary>
  );
}
