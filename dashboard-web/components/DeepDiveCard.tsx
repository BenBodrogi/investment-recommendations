import type { DeepDive } from "@/lib/data";
import ScoreBreakdownChart from "./ScoreBreakdownChart";
import ReturnRangeChart from "./ReturnRangeChart";

export default function DeepDiveCard({ dive }: { dive: DeepDive }) {
  return (
    <div className="rounded-lg border border-border-hairline bg-surface p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold text-foreground">{dive.symbol}</h3>
        <span className="text-sm text-text-muted">{dive.group}</span>
      </div>
      <div className="text-2xl font-bold tabular-nums text-foreground">
        ${dive.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </div>
      <p className="mt-2 text-sm text-text-secondary">{dive.current_situation}</p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1 text-xs uppercase tracking-wide text-text-muted">
            Score breakdown
          </div>
          <ScoreBreakdownChart breakdown={dive.score_breakdown} />
        </div>
        <div>
          <div className="mb-1 text-xs uppercase tracking-wide text-text-muted">
            12-month return estimate
          </div>
          <ReturnRangeChart estimate={dive.return_estimate} />
          <p className="mt-1 text-xs text-text-muted">{dive.return_estimate.caveat}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-status-good">
            Strengths
          </div>
          <ul className="list-inside list-disc space-y-1 text-sm text-text-secondary">
            {dive.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-status-critical">
            Weaknesses
          </div>
          <ul className="list-inside list-disc space-y-1 text-sm text-text-secondary">
            {dive.weaknesses.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      </div>

      {dive.sections_omitted.length > 0 && (
        <p className="mt-3 text-xs text-text-muted">
          Not available this run: {dive.sections_omitted.join(", ")}
        </p>
      )}
    </div>
  );
}
