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

export default function DataFreshness({ generatedAtUtc }: { generatedAtUtc: string }) {
  const [label, setLabel] = useState(() => relativeTime(generatedAtUtc));

  useEffect(() => {
    const id = setInterval(() => setLabel(relativeTime(generatedAtUtc)), 60_000);
    return () => clearInterval(id);
  }, [generatedAtUtc]);

  const ageDays = (Date.now() - new Date(generatedAtUtc).getTime()) / 86_400_000;
  const stale = ageDays > STALE_AFTER_DAYS;

  return (
    <span
      className={`text-sm ${stale ? "text-status-critical font-medium" : "text-text-muted"}`}
      title={new Date(generatedAtUtc).toLocaleString()}
    >
      Last updated {label}
      {stale ? " — consider refreshing" : ""}
    </span>
  );
}
