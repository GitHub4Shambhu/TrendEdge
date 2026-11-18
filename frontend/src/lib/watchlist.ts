/**
 * TrendEdge Frontend - Watchlist Store
 *
 * Keeps the user's watchlist in localStorage and, when the backend is
 * reachable, mirrors it to the server so the scheduled signal-change check
 * can score it.  The server copy wins on load; an empty server list is
 * seeded from the browser copy.  Without a backend it stays local-only.
 */

"use client";

import { useCallback, useSyncExternalStore } from "react";
import { apiClient, SavedWatchlistEntry } from "@/lib/api";

const STORAGE_KEY = "trendedge:watchlist";
export const WATCHLIST_MAX = 25;
const DEFAULT_WATCHLIST = ["NVDA", "AAPL", "MSFT"];

interface WatchlistState {
  symbols: string[];
  /** Symbols with signal-change alerts switched off */
  alertsOff: ReadonlySet<string>;
  /** True once the server copy has been loaded */
  synced: boolean;
}

const SERVER_STATE: WatchlistState = { symbols: [], alertsOff: new Set(), synced: false };

const listeners = new Set<() => void>();
let state: WatchlistState | null = null;
let syncStarted = false;

function readLocal(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : DEFAULT_WATCHLIST;
    return Array.isArray(parsed)
      ? parsed.filter((s): s is string => typeof s === "string")
      : DEFAULT_WATCHLIST;
  } catch {
    return DEFAULT_WATCHLIST;
  }
}

function read(): WatchlistState {
  if (!state) state = { symbols: readLocal(), alertsOff: new Set(), synced: false };
  return state;
}

function setState(next: Partial<WatchlistState>) {
  const prev = read();
  state = { ...prev, ...next };
  if (next.symbols && next.symbols !== prev.symbols) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next.symbols));
    } catch {
      // Storage unavailable (private mode, quota) — keep in-memory only
    }
  }
  listeners.forEach((l) => l());
}

function applyServer(entries: SavedWatchlistEntry[]) {
  setState({
    symbols: entries.map((e) => e.symbol),
    alertsOff: new Set(entries.filter((e) => !e.alerts_enabled).map((e) => e.symbol)),
    synced: true,
  });
}

async function syncFromServer() {
  try {
    const { symbols } = await apiClient.getSavedWatchlist();
    if (symbols.length > 0) {
      applyServer(symbols);
    } else {
      applyServer((await apiClient.saveWatchlist(read().symbols)).symbols);
    }
  } catch {
    // Backend unavailable — stay local-only (alerts disabled)
  }
}

function writeSymbols(next: string[]) {
  setState({ symbols: next });
  if (read().synced) {
    apiClient.saveWatchlist(next).catch((err) => console.warn("Watchlist save failed:", err));
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!syncStarted) {
    syncStarted = true;
    syncFromServer();
  }
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      state = { ...read(), symbols: readLocal() };
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useWatchlist() {
  const { symbols, alertsOff, synced } = useSyncExternalStore(subscribe, read, () => SERVER_STATE);

  const add = useCallback((symbol: string) => {
    const s = symbol.trim().toUpperCase();
    const current = read().symbols;
    if (!s || current.includes(s) || current.length >= WATCHLIST_MAX) return;
    writeSymbols([...current, s]);
  }, []);

  const remove = useCallback((symbol: string) => {
    writeSymbols(read().symbols.filter((s) => s !== symbol));
  }, []);

  const has = useCallback((symbol: string) => symbols.includes(symbol), [symbols]);

  const alertsEnabled = useCallback((symbol: string) => !alertsOff.has(symbol), [alertsOff]);

  const toggleAlerts = useCallback(async (symbol: string) => {
    const enable = read().alertsOff.has(symbol);
    try {
      applyServer((await apiClient.setAlertsEnabled(symbol, enable)).symbols);
    } catch (err) {
      console.warn("Alert toggle failed:", err);
    }
  }, []);

  return {
    symbols,
    add,
    remove,
    has,
    isFull: symbols.length >= WATCHLIST_MAX,
    /** Whether the list is saved on the server (alerts available) */
    synced,
    alertsEnabled,
    toggleAlerts,
  };
}
