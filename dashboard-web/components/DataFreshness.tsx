"use client";

import { useEffect, useState } from "react";

function relativeTime(fromIso: string): string {
  const ms = Date.now() - new Date(fromIso).getTime();
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

const STALE_AFTER_DAYS = 8; // a bit past the suggested weekly cadence

function isStale(fromIso: string): boolean {
  const ageDays = (Date.now() - new Date(fromIso).getTime()) / 86_400_000;
  return ageDays > STALE_AFTER_DAYS;
}

export default function DataFreshness({ generatedAtUtc }: { generatedAtUtc: string }) {
  const [label, setLabel] = useState(() => relativeTime(generatedAtUtc));
  const [stale, setStale] = useState(() => isStale(generatedAtUtc));

  // Re-derive when generatedAtUtc changes - router.refresh() updates this
  // prop without remounting the component, so without this, label/stale
  // would keep showing pre-refresh values until the next 60s tick. The
  // update only ever runs inside a timer callback (never synchronously in
  // the effect body), so this doesn't trip react-hooks/set-state-in-effect;
  // Date.now() only ever runs inside that callback or the useState
  // initializers above, never directly in the render body, so it doesn't
  // trip react-hooks/purity or risk a hydration mismatch either.
  useEffect(() => {
    const update = () => {
      setLabel(relativeTime(generatedAtUtc));
      setStale(isStale(generatedAtUtc));
    };
    const immediate = setTimeout(update, 0);
    const interval = setInterval(update, 60_000);
    return () => {
      clearTimeout(immediate);
      clearInterval(interval);
    };
  }, [generatedAtUtc]);

  return (
    <span
      className={`text-sm ${stale ? "text-status-critical font-medium" : "text-text-muted"}`}
      title={new Date(generatedAtUtc).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "medium" })}
    >
      Last updated {label}
      {stale ? " — consider refreshing" : ""}
    </span>
  );
}
