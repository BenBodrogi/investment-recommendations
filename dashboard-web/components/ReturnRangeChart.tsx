"use client";

import {
  Bar,
  ComposedChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { ReturnEstimate } from "@/lib/data";

export default function ReturnRangeChart({ estimate }: { estimate: ReturnEstimate }) {
  const { low_pct, high_pct, central_pct } = estimate;
  const good = central_pct >= 0;
  const color = good ? "var(--status-good)" : "var(--status-critical)";

  const padding = 5;
  const domainLow = Math.min(low_pct, 0) - padding;
  const domainHigh = Math.max(high_pct, 0) + padding;

  const data = [{ row: "range", span: [low_pct, high_pct] as [number, number] }];

  return (
    <div>
      <ResponsiveContainer width="100%" height={56}>
        <ComposedChart
          layout="vertical"
          data={data}
          margin={{ top: 8, right: 16, bottom: 8, left: 16 }}
        >
          <XAxis type="number" domain={[domainLow, domainHigh]} hide />
          <YAxis type="category" dataKey="row" hide />
          <ReferenceLine x={0} stroke="var(--gridline)" strokeDasharray="3 3" />
          <Bar dataKey="span" fill={color} fillOpacity={0.35} radius={4} barSize={12} />
          <ReferenceDot x={central_pct} y="range" r={5} fill={color} stroke="var(--surface)" strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="-mt-2 flex justify-between text-xs text-text-muted tabular-nums">
        <span>{low_pct.toFixed(1)}%</span>
        <span className="font-semibold" style={{ color }}>
          {central_pct >= 0 ? "+" : ""}
          {central_pct.toFixed(1)}% central
        </span>
        <span>{high_pct.toFixed(1)}%</span>
      </div>
    </div>
  );
}
