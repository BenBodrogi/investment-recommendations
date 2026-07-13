import { getDashboardData } from "@/lib/data";
import Dashboard from "@/components/Dashboard";

// Always render fresh - this page reads output/dashboard_data.json off disk,
// which changes every time the Refresh button (or a scheduled run) executes
// the Python pipeline. Never let this get statically cached.
export const dynamic = "force-dynamic";

export default function Home() {
  const data = getDashboardData();
  return <Dashboard initialData={data} />;
}
