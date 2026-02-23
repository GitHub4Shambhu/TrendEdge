"use client";

/**
 * DataSourceBadge - Shows whether data is live or stale/mock.
 *
 * Displays a small badge:
 *  - Green "● Live" when data_source === "live"
 *  - Yellow/amber "⚠ Stale Data" when data_source === "stale"
 */

export default function DataSourceBadge({
  dataSource,
}: {
  dataSource?: string;
}) {
  if (!dataSource) return null;

  const isLive = dataSource === "live";

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide uppercase ${
        isLive
          ? "bg-green-500/15 text-green-400 border border-green-500/30"
          : "bg-amber-500/15 text-amber-400 border border-amber-500/30 animate-pulse"
      }`}
    >
      {isLive ? (
        <>
          <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
          Live
        </>
      ) : (
        <>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          Stale Data
        </>
      )}
    </span>
  );
}
