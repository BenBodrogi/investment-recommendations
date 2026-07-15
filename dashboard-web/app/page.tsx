import { findDeepDive, getDashboardData } from "@/lib/data";
import Dashboard from "@/components/Dashboard";

// Always render fresh - this page reads dashboard-web/data/dashboard_data.json
// off disk, which changes every time the Refresh button (locally) or the
// scheduled GitHub Action (deployed) writes a new one. Never let this get
// statically cached.
export const dynamic = "force-dynamic";

export default function Home() {
  const data = getDashboardData();
  const canRefresh = Boolean(process.env.PIPELINE_PYTHON);
  // Resolved server-side (this is a Server Component, so lib/data.ts's
  // node:fs import is fine here) - Dashboard is a Client Component and must
  // never import a value (only types) from lib/data.ts, or Turbopack tries
  // to bundle node:fs for the browser and the build breaks.
  const bestChoiceDeepDive = data
    ? findDeepDive(data, data.best_choice.symbol, data.best_choice.asset_class)
    : undefined;
  return <Dashboard initialData={data} canRefresh={canRefresh} bestChoiceDeepDive={bestChoiceDeepDive} />;
}
