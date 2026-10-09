/**
 * TrendEdge Frontend - Watchlist Store
 *
 * Persists the user's watchlist in localStorage and keeps every component
 * that uses it (search panel, watchlist table) in sync.
 */

"use client";

import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "trendedge:watchlist";
export const WATCHLIST_MAX = 25;
const DEFAULT_WATCHLIST = ["NVDA", "AAPL", "MSFT"];
const EMPTY: string[] = [];

const listeners = new Set<() => void>();
let cache: string[] | null = null;

function read(): string[] {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : DEFAULT_WATCHLIST;
    cache = Array.isArray(parsed)
      ? parsed.filter((s): s is string => typeof s === "string")
      : DEFAULT_WATCHLIST;
  } catch {
    cache = DEFAULT_WATCHLIST;
  }
  return cache;
}

function write(next: string[]) {
  cache = next;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage unavailable (private mode, quota) — keep in-memory only
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      cache = null;
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
  const symbols = useSyncExternalStore(subscribe, read, () => EMPTY);

  const add = useCallback((symbol: string) => {
    const s = symbol.trim().toUpperCase();
    const current = read();
    if (!s || current.includes(s) || current.length >= WATCHLIST_MAX) return;
    write([...current, s]);
  }, []);

  const remove = useCallback((symbol: string) => {
    write(read().filter((s) => s !== symbol));
  }, []);

  const has = useCallback((symbol: string) => symbols.includes(symbol), [symbols]);

  return { symbols, add, remove, has, isFull: symbols.length >= WATCHLIST_MAX };
}
