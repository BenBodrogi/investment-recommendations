import fs from "node:fs";
import path from "node:path";

export interface MacroBackdrop {
  fed_funds_rate: number | null;
  cpi_yoy: number | null;
  unemployment_rate: number | null;
  treasury_10y: number | null;
  narrative: string;
}

export interface ScoredSymbol {
  symbol: string;
  asset_class: "stock" | "etf" | "crypto";
  group: string;
  composite_score: number;
  score_breakdown: Record<string, number>;
  price: number;
  day_change_pct: number | null;
  data_quality_notes: string[];
}

export interface ReturnEstimate {
  central_pct: number;
  low_pct: number;
  high_pct: number;
  horizon_months: number;
  caveat: string;
}

export interface DeepDive {
  symbol: string;
  asset_class: "stock" | "etf" | "crypto";
  group: string;
  composite_score: number;
  score_breakdown: Record<string, number>;
  price: number;
  current_situation: string;
  strengths: string[];
  weaknesses: string[];
  return_estimate: ReturnEstimate;
  sections_omitted: string[];
}

export interface DataQuality {
  sources_attempted: string[];
  sources_fully_unavailable: string[];
  symbols_skipped: { symbol: string; reason: string }[];
  deep_dive_sections_omitted: { symbol: string; section: string }[];
  run_duration_seconds: number;
}

export interface DashboardData {
  generated_at_utc: string;
  disclaimer: string;
  macro_backdrop: MacroBackdrop;
  watchlist_summary: ScoredSymbol[];
  best_choice: ScoredSymbol;
  deep_dives: {
    stock?: DeepDive[];
    etf?: DeepDive[];
    crypto?: DeepDive[];
  };
  data_quality: DataQuality;
}

/** The featured pick's own deep dive, for its narrative content
 * (situation/strengths/return estimate). The global top score is always
 * within its asset class's deep-dive shortlist by construction, so this
 * should always resolve - callers should still handle `undefined`. */
export function findDeepDive(data: DashboardData, symbol: string): DeepDive | undefined {
  for (const assetClass of ["stock", "etf", "crypto"] as const) {
    const match = data.deep_dives[assetClass]?.find((d) => d.symbol === symbol);
    if (match) return match;
  }
  return undefined;
}

export function pipelineDir(): string {
  const dir = process.env.PIPELINE_DIR;
  if (!dir) {
    throw new Error("PIPELINE_DIR is not set - check .env.local");
  }
  return dir;
}

export function dashboardDataPath(): string {
  return path.join(process.cwd(), "data", "dashboard_data.json");
}

export function pipelinePythonPath(): string {
  const py = process.env.PIPELINE_PYTHON;
  if (!py) {
    throw new Error("PIPELINE_PYTHON is not set - check .env.local");
  }
  return py;
}

/** Returns null if the pipeline hasn't been run yet - the UI shows a
 * "no data yet, click refresh" state rather than crashing. */
export function getDashboardData(): DashboardData | null {
  const filePath = dashboardDataPath();
  if (!fs.existsSync(filePath)) {
    return null;
  }
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as DashboardData;
}
