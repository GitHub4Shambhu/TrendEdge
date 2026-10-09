/**
 * TrendEdge Frontend - Watchlist Component
 *
 * Personal list of tickers (persisted in the browser) with the latest
 * signal from every momentum engine and their consensus.
 */

"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiClient, WatchlistResponse } from "@/lib/api";
import { useWatchlist, WATCHLIST_MAX } from "@/lib/watchlist";
import { formatCurrency, formatPercent, getValueColor } from "@/lib/utils";
import DataSourceBadge from "./DataSourceBadge";
import { ConsensusBadge, SignalPill } from "./SignalBadges";

function Score({ value, digits = 2 }: { value: number | null; digits?: number }) {
  if (value === null) return null;
  return <span className="text-[11px] text-gray-500 tabular-nums ml-1.5">{value.toFixed(digits)}</span>;
}

export default function Watchlist() {
  const { symbols, add, remove, isFull } = useWatchlist();
  const [data, setData] = useState<WatchlistResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");

  const symbolsKey = symbols.join(",");

  const fetchData = useCallback(async () => {
    if (!symbolsKey) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await apiClient.getWatchlist(symbolsKey.split(",")));
    } catch {
      setError("Could not load watchlist — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [symbolsKey]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onAdd = (e: FormEvent) => {
    e.preventDefault();
    input
      .split(/[\s,]+/)
      .filter(Boolean)
      .forEach(add);
    setInput("");
  };

  // Keep rows in the user's order; show placeholders for symbols still loading
  const rows = symbols.map((s) => data?.items.find((i) => i.symbol === s) ?? s);
  const notFound = new Set(data?.not_found ?? []);

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-4 sm:px-6 py-4 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>
            {symbols.length}/{WATCHLIST_MAX} symbols
          </span>
          <DataSourceBadge dataSource={data?.data_source} />
        </div>
        <div className="flex gap-2">
          <form onSubmit={onAdd} className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value.toUpperCase())}
              placeholder={isFull ? "Watchlist full" : "Add ticker(s)"}
              disabled={isFull}
              aria-label="Add ticker to watchlist"
              className="w-36 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 font-mono focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isFull || !input.trim()}
              className="px-3 py-1.5 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Add
            </button>
          </form>
          <button
            onClick={fetchData}
            disabled={loading || symbols.length === 0}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-400 hover:text-white disabled:opacity-50"
          >
            {loading ? "…" : "↻"}
          </button>
        </div>
      </div>

      {error && <p className="px-6 py-3 text-sm text-red-400">{error}</p>}

      {symbols.length === 0 ? (
        <p className="px-6 py-10 text-center text-sm text-gray-500">
          Your watchlist is empty. Add a ticker above, or use ☆ Watch on a search result.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-gray-500 border-b border-gray-800">
                <th className="px-4 sm:px-6 py-2.5 font-medium">Symbol</th>
                <th className="px-3 py-2.5 font-medium text-right">Price</th>
                <th className="px-3 py-2.5 font-medium text-right">1D</th>
                <th className="px-3 py-2.5 font-medium">Advanced AI</th>
                <th className="px-3 py-2.5 font-medium">Max Risk</th>
                <th className="px-3 py-2.5 font-medium">Institutional</th>
                <th className="px-3 py-2.5 font-medium">Consensus</th>
                <th className="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/70">
              {rows.map((row) => {
                const symbol = typeof row === "string" ? row : row.symbol;
                return (
                  <tr key={symbol} className="hover:bg-gray-800/30">
                    <td className="px-4 sm:px-6 py-3 font-mono font-bold text-white whitespace-nowrap">
                      {symbol}
                      {typeof row !== "string" && row.data_source === "stale" && (
                        <span className="ml-1.5 text-amber-400" title="No live data — simulated values">⚠</span>
                      )}
                    </td>
                    {typeof row === "string" ? (
                      <td colSpan={6} className="px-3 py-3 text-xs text-gray-500">
                        {notFound.has(symbol) ? "Could not analyze this symbol" : loading ? "Loading…" : "—"}
                      </td>
                    ) : (
                      <>
                        <td className="px-3 py-3 text-right text-gray-200 tabular-nums">{formatCurrency(row.price)}</td>
                        <td className={`px-3 py-3 text-right tabular-nums ${getValueColor(row.price_change_pct)}`}>
                          {formatPercent(row.price_change_pct)}
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <SignalPill signal={row.advanced_signal} />
                          <Score value={row.advanced_score !== null ? row.advanced_score * 100 : null} digits={1} />
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <SignalPill signal={row.max_risk_signal} />
                          <Score value={row.max_risk_score} />
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <SignalPill signal={row.institutional_signal} />
                          <Score value={row.institutional_score} />
                        </td>
                        <td className="px-3 py-3">
                          <ConsensusBadge consensus={row.consensus} />
                        </td>
                      </>
                    )}
                    <td className="px-3 py-3 text-right">
                      <button
                        onClick={() => remove(symbol)}
                        aria-label={`Remove ${symbol}`}
                        className="text-gray-600 hover:text-red-400"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
