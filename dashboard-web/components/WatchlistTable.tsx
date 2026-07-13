"use client";

import { useMemo, useState } from "react";
import type { ScoredSymbol } from "@/lib/data";

type SortKey = "symbol" | "asset_class" | "group" | "composite_score" | "price" | "day_change_pct";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "symbol", label: "Symbol" },
  { key: "asset_class", label: "Class" },
  { key: "group", label: "Group" },
  { key: "composite_score", label: "Score" },
  { key: "price", label: "Price" },
  { key: "day_change_pct", label: "Day change" },
];

function DayChange({ value }: { value: number | null }) {
  if (value === null) return <span className="text-text-muted">—</span>;
  const good = value >= 0;
  return (
    <span
      className="font-medium tabular-nums"
      style={{ color: good ? "var(--status-good)" : "var(--status-critical)" }}
    >
      {good ? "▲" : "▼"} {Math.abs(value).toFixed(2)}%
    </span>
  );
}

export default function WatchlistTable({ rows }: { rows: ScoredSymbol[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      let cmp: number;
      if (typeof av === "number" && typeof bv === "number") {
        cmp = av - bv;
      } else {
        cmp = String(av ?? "").localeCompare(String(bv ?? ""));
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border-hairline">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-border-hairline bg-surface">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="cursor-pointer select-none px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-text-muted hover:text-foreground"
              >
                {col.label}
                {sortKey === col.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.symbol} className="border-b border-border-hairline last:border-0 hover:bg-surface">
              <td className="px-3 py-2 font-semibold text-foreground">{row.symbol}</td>
              <td className="px-3 py-2 text-text-secondary capitalize">{row.asset_class}</td>
              <td className="px-3 py-2 text-text-secondary">{row.group}</td>
              <td className="px-3 py-2 tabular-nums text-foreground">{row.composite_score.toFixed(1)}</td>
              <td className="px-3 py-2 tabular-nums text-foreground">
                ${row.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </td>
              <td className="px-3 py-2">
                <DayChange value={row.day_change_pct} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
