import type { MacroBackdrop } from "@/lib/data";

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border-hairline bg-surface px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-foreground tabular-nums">
        {value}
      </div>
    </div>
  );
}

function fmtPct(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(2)}%`;
}

export default function MacroStatRow({ macro }: { macro: MacroBackdrop }) {
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Fed funds rate" value={fmtPct(macro.fed_funds_rate)} />
        <StatTile label="CPI (YoY)" value={fmtPct(macro.cpi_yoy)} />
        <StatTile label="Unemployment" value={fmtPct(macro.unemployment_rate)} />
        <StatTile label="10Y Treasury" value={fmtPct(macro.treasury_10y)} />
      </div>
      <p className="mt-2 text-sm text-text-secondary">{macro.narrative}</p>
    </div>
  );
}
