/**
 * TrendEdge Frontend - Signal Alerts Feed
 *
 * Recent watchlist consensus changes detected by the backend's scheduled
 * check, with a button to run the check immediately.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient, AlertEventsResponse } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { ConsensusBadge } from "./SignalBadges";

export default function SignalAlerts({ symbolsKey }: { symbolsKey: string }) {
  const [data, setData] = useState<AlertEventsResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await apiClient.getAlertEvents(10));
      setError(null);
    } catch {
      setError("Could not load signal alerts.");
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [load, symbolsKey]);

  const checkNow = async () => {
    setChecking(true);
    try {
      setData(await apiClient.checkAlertsNow(10));
      setError(null);
    } catch {
      setError("Signal check failed.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="border-t border-gray-800 px-4 sm:px-6 py-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-white">🔔 Recent signal changes</h3>
          <p className="text-xs text-gray-500">
            Checked every 30 min while the market is open
            {data?.last_check && ` · last check ${formatRelativeTime(data.last_check)}`}
            {data && !data.webhook_configured && " · no webhook set, in-app only"}
          </p>
        </div>
        <button
          onClick={checkNow}
          disabled={checking}
          className="self-start sm:self-auto px-3 py-1.5 rounded-lg text-xs bg-gray-800 border border-gray-700 text-gray-300 hover:text-white disabled:opacity-50"
        >
          {checking ? "Checking…" : "Check now"}
        </button>
      </div>

      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}

      {data && data.events.length === 0 ? (
        <p className="text-xs text-gray-500">
          No changes yet. The first check records each ticker&apos;s current consensus; later checks
          alert when it flips.
        </p>
      ) : (
        <ul className="space-y-2">
          {data?.events.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono font-bold text-white w-14">{e.symbol}</span>
              <ConsensusBadge consensus={e.previous} />
              <span className="text-gray-500">→</span>
              <ConsensusBadge consensus={e.current} />
              <span className="text-gray-400 tabular-nums">{formatCurrency(e.price)}</span>
              <span className="text-xs text-gray-500 ml-auto">{formatRelativeTime(e.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
