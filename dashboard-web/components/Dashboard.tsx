"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { DashboardData, DeepDive } from "@/lib/data";
import DisclaimerBanner from "./DisclaimerBanner";
import DataFreshness from "./DataFreshness";
import MacroStatRow from "./MacroStatRow";
import WatchlistTable from "./WatchlistTable";
import DeepDiveCard from "./DeepDiveCard";
import BestChoiceCard from "./BestChoiceCard";

const ASSET_CLASS_LABEL: Record<string, string> = {
  stock: "Stocks",
  etf: "ETFs",
  crypto: "Crypto",
};

const SCORE_FACTOR_LEGEND: { name: string; color: string }[] = [
  { name: "Valuation", color: "var(--series-1)" },
  { name: "Momentum", color: "var(--series-2)" },
  { name: "Volatility", color: "var(--series-3)" },
  { name: "Yield", color: "var(--series-4)" },
];

export default function Dashboard({
  initialData,
  canRefresh,
  bestChoiceDeepDive,
}: {
  initialData: DashboardData | null;
  canRefresh: boolean;
  bestChoiceDeepDive: DeepDive | undefined;
}) {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" });
  }, [logs]);

  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  function startRefresh() {
    if (refreshing) return;
    setRefreshing(true);
    setLogs([]);
    setError(null);

    const es = new EventSource("/api/refresh");
    esRef.current = es;
    // The browser's native EventSource fires its own generic "error" event
    // whenever the underlying connection closes - including right after a
    // clean server-side close following our "done" message. Without this
    // guard, a successful run still shows a spurious "connection failed"
    // error because both events land for the same stream teardown.
    let finished = false;

    es.addEventListener("log", (e: MessageEvent) => {
      setLogs((prev) => [...prev, JSON.parse(e.data) as string]);
    });

    es.addEventListener("done", (e: MessageEvent) => {
      finished = true;
      const code = JSON.parse(e.data) as string;
      es.close();
      esRef.current = null;
      setRefreshing(false);
      if (code !== "0") {
        setError(`Pipeline exited with code ${code} - check the log above.`);
      }
      router.refresh();
    });

    es.addEventListener("error", (e: Event) => {
      if (finished) return;
      finished = true;
      let message = "Connection to the refresh stream failed.";
      if (e instanceof MessageEvent && e.data) {
        try {
          message = JSON.parse(e.data) as string;
        } catch {
          // not our named event, fall through to default message
        }
      }
      setError(message);
      es.close();
      esRef.current = null;
      setRefreshing(false);
    });
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Investment Recommendations</h1>
          {initialData && <DataFreshness generatedAtUtc={initialData.generated_at_utc} />}
        </div>
        {canRefresh ? (
          <button
            onClick={startRefresh}
            disabled={refreshing}
            className="rounded-md bg-series-1 px-4 py-2 font-medium text-white disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh now"}
          </button>
        ) : (
          <span className="text-sm text-text-muted">Data refreshes automatically</span>
        )}
      </header>

      {(refreshing || logs.length > 0) && (
        <div className="rounded-md border border-border-hairline bg-surface p-3">
          <div className="max-h-40 overflow-y-auto whitespace-pre-wrap font-mono text-xs text-text-secondary">
            {logs.length === 0 ? "Starting pipeline…" : logs.join("")}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-status-critical/40 bg-status-critical/10 px-4 py-3 text-sm text-status-critical">
          {error}
        </div>
      )}

      {!initialData ? (
        <div className="rounded-lg border border-border-hairline bg-surface p-8 text-center text-text-secondary">
          No data yet — click &quot;Refresh now&quot; to run the pipeline (takes about 2 minutes).
        </div>
      ) : (
        <>
          <DisclaimerBanner text={initialData.disclaimer} />
          <BestChoiceCard pick={initialData.best_choice} deepDive={bestChoiceDeepDive} />
          <MacroStatRow macro={initialData.macro_backdrop} />

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold text-foreground">Deep dives</h2>
              <div className="flex gap-3 text-xs text-text-muted">
                {SCORE_FACTOR_LEGEND.map((f) => (
                  <span key={f.name} className="flex items-center gap-1">
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: f.color }}
                    />
                    {f.name}
                  </span>
                ))}
              </div>
            </div>
            {(["stock", "etf", "crypto"] as const).map((assetClass) => {
              const dives = initialData.deep_dives[assetClass];
              if (!dives || dives.length === 0) return null;
              return (
                <div key={assetClass} className="mb-4">
                  <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-muted">
                    {ASSET_CLASS_LABEL[assetClass]}
                  </h3>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {dives.map((dive) => (
                      <DeepDiveCard key={dive.symbol} dive={dive} />
                    ))}
                  </div>
                </div>
              );
            })}
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-foreground">Watchlist</h2>
            <WatchlistTable rows={initialData.watchlist_summary} />
          </section>

          {(initialData.data_quality.sources_fully_unavailable.length > 0 ||
            initialData.data_quality.symbols_skipped.length > 0) && (
            <section className="text-xs text-text-muted">
              <p>
                Data quality: {initialData.data_quality.run_duration_seconds.toFixed(0)}s run.
                {initialData.data_quality.sources_fully_unavailable.length > 0 &&
                  ` Unavailable this run: ${initialData.data_quality.sources_fully_unavailable.join(", ")}.`}
                {initialData.data_quality.symbols_skipped.length > 0 &&
                  ` Skipped: ${initialData.data_quality.symbols_skipped.map((s) => s.symbol).join(", ")}.`}
              </p>
            </section>
          )}
        </>
      )}
    </div>
  );
}
