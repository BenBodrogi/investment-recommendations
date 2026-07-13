"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";

// Fixed name -> categorical slot mapping, used everywhere this factor
// appears across the dashboard. Never assigned by array position/rank -
// "yield" is always slot 4 whether or not "momentum" happens to be present.
const FACTOR_COLOR: Record<string, string> = {
  valuation: "var(--series-1)",
  momentum: "var(--series-2)",
  volatility: "var(--series-3)",
  yield: "var(--series-4)",
};

const FACTOR_ORDER = ["valuation", "momentum", "volatility", "yield"];

export default function ScoreBreakdownChart({
  breakdown,
}: {
  breakdown: Record<string, number>;
}) {
  const data = FACTOR_ORDER.filter((f) => f in breakdown).map((factor) => ({
    factor: factor[0].toUpperCase() + factor.slice(1),
    value: breakdown[factor],
    color: FACTOR_COLOR[factor],
  }));

  return (
    <ResponsiveContainer width="100%" height={data.length * 32 + 8}>
      <BarChart
        layout="vertical"
        data={data}
        margin={{ top: 0, right: 28, bottom: 0, left: 0 }}
      >
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          type="category"
          dataKey="factor"
          width={72}
          tickLine={false}
          axisLine={false}
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
        />
        <Bar dataKey="value" radius={4} barSize={14}>
          {data.map((entry) => (
            <Cell key={entry.factor} fill={entry.color} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(0) : "")}
            style={{ fill: "var(--foreground)", fontSize: 12 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
