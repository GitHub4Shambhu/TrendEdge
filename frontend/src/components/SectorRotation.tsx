/**
 * TrendEdge Frontend - Sector Rotation Heatmap
 *
 * The 11 Select Sector SPDR ETFs across 1W → 12M horizons, plus relative
 * strength vs SPY and distance to the 200DMA. Cells are shaded by magnitude
 * within their column so rotation (short-term vs long-term leaders) stands out.
 */

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient, SectorPerformance, SectorRotationResponse } from "@/lib/api";
import { cn, formatPercent } from "@/lib/utils";
import { MOCK_SECTOR_ROTATION } from "@/lib/demoData";
import DataSourceBadge from "./DataSourceBadge";
import { SignalPill } from "./SignalBadges";

type MetricKey = "r1w" | "r1m" | "r3m" | "r6m" | "r12m" | "rs3m" | "distance_to_200dma" | "momentum_score";

const COLUMNS: { key: MetricKey; label: string; title: string; isPct: boolean }[] = [
  { key: "r1w", label: "1W", title: "1-week return", isPct: true },
  { key: "r1m", label: "1M", title: "1-month return", isPct: true },
  { key: "r3m", label: "3M", title: "3-month return", isPct: true },
  { key: "r6m", label: "6M", title: "6-month return", isPct: true },
  { key: "r12m", label: "12M", title: "12-month return", isPct: true },
  { key: "rs3m", label: "RS 3M", title: "3-month return minus SPY", isPct: true },
  { key: "distance_to_200dma", label: "vs 200D", title: "% above/below 200-day moving average", isPct: true },
  { key: "momentum_score", label: "Score", title: "Max Risk momentum score", isPct: false },
];

function cellStyle(value: number, maxAbs: number): React.CSSProperties {
  if (maxAbs === 0 || value === 0) return {};
  const alpha = 0.12 + 0.5 * Math.min(Math.abs(value) / maxAbs, 1);
  return {
    backgroundColor: value > 0 ? `rgba(16, 185, 129, ${alpha})` : `rgba(239, 68, 68, ${alpha})`,
  };
}

export default function SectorRotation() {
  const [data, setData] = useState<SectorRotationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [useMock, setUseMock] = useState(false);
  const [sortKey, setSortKey] = useState<MetricKey>("momentum_score");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await apiClient.getSectorRotation());
      setUseMock(false);
    } catch (err) {
      if (err instanceof Error && err.message.startsWith("API Error")) {
        setError("Could not load sector data.");
      } else {
        console.warn("API unavailable, using demo data:", err);
        setData(MOCK_SECTOR_ROTATION);
        setUseMock(true);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const sorted = useMemo(
    () => [...(data?.sectors ?? [])].sort((a, b) => b[sortKey] - a[sortKey]),
    [data, sortKey]
  );

  const maxAbs = useMemo(() => {
    const out = {} as Record<MetricKey, number>;
    for (const c of COLUMNS) {
      out[c.key] = Math.max(0, ...(data?.sectors ?? []).map((s) => Math.abs(s[c.key])));
    }
    return out;
  }, [data]);

  const nameOf = (sym: string) => data?.sectors.find((s) => s.symbol === sym)?.name ?? sym;

  if (loading && !data) {
    return (
      <div className="bg-gray-900/60 rounded-xl border border-gray-800 p-8 flex items-center justify-center h-48">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-500" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-gray-900/60 rounded-xl border border-gray-800 p-8 text-center">
        <p className="text-sm text-red-400 mb-3">{error}</p>
        <button onClick={fetchData} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
          Retry
        </button>
      </div>
    );
  }

  const renderRow = (s: SectorPerformance, isBenchmark = false) => (
    <tr key={s.symbol} className={cn(isBenchmark && "border-t-2 border-gray-700 bg-gray-800/40")}>
      <td className="px-4 sm:px-6 py-2.5 whitespace-nowrap">
        <span className="font-mono font-bold text-white">{s.symbol}</span>
        <span className="ml-2 text-xs text-gray-500">{s.name}</span>
      </td>
      {COLUMNS.map((c) => (
        <td
          key={c.key}
          className="px-2 py-2.5 text-right tabular-nums text-gray-100"
          style={isBenchmark ? undefined : cellStyle(s[c.key], maxAbs[c.key])}
        >
          {c.isPct ? formatPercent(s[c.key], 1) : s[c.key].toFixed(1)}
        </td>
      ))}
      <td className="px-3 py-2.5 text-center">{!isBenchmark && <SignalPill signal={s.signal} />}</td>
    </tr>
  );

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-4 sm:px-6 py-4 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="text-gray-500">
            Leading:{" "}
            <span className="text-green-400 font-medium">{data.leaders.map(nameOf).join(", ")}</span>
          </span>
          {data.laggards.length > 0 && (
            <span className="text-gray-500">
              Lagging:{" "}
              <span className="text-red-400 font-medium">{data.laggards.map(nameOf).join(", ")}</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {useMock && <span className="text-xs text-yellow-500">(Demo)</span>}
          <DataSourceBadge dataSource={data.data_source} />
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-400 hover:text-white disabled:opacity-50"
          >
            {loading ? "…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-gray-500 border-b border-gray-800">
              <th className="px-4 sm:px-6 py-2.5 text-left font-medium">Sector</th>
              {COLUMNS.map((c) => (
                <th key={c.key} className="px-2 py-2.5 text-right font-medium" title={c.title}>
                  <button
                    onClick={() => setSortKey(c.key)}
                    className={cn("uppercase hover:text-white", sortKey === c.key && "text-teal-400")}
                  >
                    {c.label}
                    {sortKey === c.key && " ↓"}
                  </button>
                </th>
              ))}
              <th className="px-3 py-2.5 font-medium">Signal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {sorted.map((s) => renderRow(s))}
            {data.benchmark && renderRow(data.benchmark, true)}
          </tbody>
        </table>
      </div>
      <p className="px-4 sm:px-6 py-2.5 text-[11px] text-gray-600 border-t border-gray-800">
        Shading is relative within each column. Click a column header to rank by that horizon.
      </p>
    </div>
  );
}
