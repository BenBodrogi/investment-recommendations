import type { DeepDive, ScoredSymbol } from "@/lib/data";
import ReturnRangeChart from "./ReturnRangeChart";

const ASSET_CLASS_LABEL: Record<string, string> = {
  stock: "Stock",
  etf: "ETF",
  crypto: "Crypto",
};

export default function BestChoiceCard({
  pick,
  deepDive,
}: {
  pick: ScoredSymbol;
  deepDive: DeepDive | undefined;
}) {
  return (
    <div className="rounded-lg border-2 border-series-1 bg-surface p-5">
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-series-1">
        Best choice this refresh
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <h2 className="text-2xl font-bold text-foreground">{pick.symbol}</h2>
          <span className="text-sm text-text-muted">
            {ASSET_CLASS_LABEL[pick.asset_class]} · {pick.group}
          </span>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold tabular-nums text-foreground">
            ${pick.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div className="text-sm text-text-muted">Score {pick.composite_score.toFixed(0)}/100</div>
        </div>
      </div>

      {deepDive ? (
        <>
          <p className="mt-2 text-sm text-text-secondary">{deepDive.current_situation}</p>
          {deepDive.strengths.length > 0 && (
            <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-text-secondary">
              {deepDive.strengths.slice(0, 3).map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          <div className="mt-4 max-w-sm">
            <div className="mb-1 text-xs uppercase tracking-wide text-text-muted">
              12-month return estimate
            </div>
            <ReturnRangeChart estimate={deepDive.return_estimate} />
            <p className="mt-1 text-xs text-text-muted">{deepDive.return_estimate.caveat}</p>
          </div>
        </>
      ) : (
        <p className="mt-2 text-sm text-text-secondary">
          Highest composite score this refresh — no deep-dive detail available for it this run.
        </p>
      )}

      <p className="mt-3 text-xs text-text-muted">
        The single highest-scoring symbol across the whole watchlist, re-evaluated on every
        refresh but only reassigned when a new leader clearly beats the current pick — not a
        recommendation to concentrate, one input among many.
      </p>
    </div>
  );
}
