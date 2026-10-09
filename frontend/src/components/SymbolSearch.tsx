/**
 * TrendEdge Frontend - Symbol Search & Deep-Dive
 *
 * Look up any ticker and see Advanced AI, Max Risk and Institutional
 * momentum side by side, with a majority-vote consensus.
 */

"use client";

import { FormEvent, ReactNode, useState } from "react";
import { apiClient, EngineSignal, SymbolLookupResponse } from "@/lib/api";
import { useWatchlist } from "@/lib/watchlist";
import { cn, formatCurrency, formatPercent, getValueColor } from "@/lib/utils";
import DataSourceBadge from "./DataSourceBadge";
import { ConsensusBadge, SignalPill } from "./SignalBadges";

const QUICK_PICKS = ["NVDA", "TSLA", "AAPL", "PLTR", "SPY", "QQQ"];

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-200 tabular-nums">{children}</span>
    </div>
  );
}

function Pct({ value }: { value: number }) {
  return <span className={getValueColor(value)}>{formatPercent(value)}</span>;
}

function EngineCard({
  title,
  accent,
  signal,
  score,
  children,
}: {
  title: string;
  accent: string;
  signal: EngineSignal | undefined;
  score: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className={cn("text-sm font-semibold", accent)}>{title}</h4>
        <SignalPill signal={signal} />
      </div>
      {score !== undefined ? (
        <>
          <div className="text-2xl font-bold text-white tabular-nums mb-3">{score}</div>
          <div className="divide-y divide-gray-700/50">{children}</div>
        </>
      ) : (
        <p className="text-sm text-gray-500">Engine could not analyze this symbol.</p>
      )}
    </div>
  );
}

export default function SymbolSearch() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SymbolLookupResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const watchlist = useWatchlist();

  const lookup = async (raw: string) => {
    const symbol = raw.trim().toUpperCase();
    if (!symbol) return;
    setQuery(symbol);
    setLoading(true);
    setError(null);
    try {
      setResult(await apiClient.lookupSymbol(symbol));
    } catch (err) {
      setResult(null);
      setError(
        err instanceof Error && err.message.includes("404")
          ? `No data found for ${symbol}.`
          : "Lookup failed — is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    lookup(query);
  };

  const adv = result?.advanced;
  const mr = result?.max_risk;
  const inst = result?.institutional;
  const inWatchlist = result ? watchlist.has(result.symbol) : false;

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800">
      {/* Search bar */}
      <div className="p-4 sm:p-6">
        <form onSubmit={onSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
            </svg>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value.toUpperCase())}
              placeholder="Search any ticker — e.g. NVDA, XLE, COIN"
              maxLength={10}
              aria-label="Ticker symbol"
              className="w-full pl-9 pr-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 font-mono uppercase placeholder:normal-case placeholder:font-sans focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium flex items-center gap-2"
          >
            {loading && <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />}
            Analyze
          </button>
        </form>
        <div className="flex flex-wrap gap-2 mt-3">
          {QUICK_PICKS.map((s) => (
            <button
              key={s}
              onClick={() => lookup(s)}
              disabled={loading}
              className="px-2.5 py-1 text-xs font-mono rounded-md bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
        {error && <p className="text-sm text-red-400 mt-3">{error}</p>}
      </div>

      {/* Result */}
      {result && (
        <div className="border-t border-gray-800 p-4 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-baseline gap-3 flex-wrap">
              <span className="text-2xl font-bold text-white font-mono">{result.symbol}</span>
              <span className="text-xl text-gray-200 tabular-nums">{formatCurrency(result.price)}</span>
              <Pct value={result.price_change_pct} />
              <DataSourceBadge dataSource={result.data_source} />
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <ConsensusBadge consensus={result.consensus} size="lg" />
                <p className="text-[11px] text-gray-500 mt-1">
                  {result.buy_votes} buy · {result.sell_votes} sell of 3 engines
                </p>
              </div>
              <button
                onClick={() =>
                  inWatchlist ? watchlist.remove(result.symbol) : watchlist.add(result.symbol)
                }
                disabled={!inWatchlist && watchlist.isFull}
                title={watchlist.isFull && !inWatchlist ? "Watchlist is full" : undefined}
                className={cn(
                  "px-3 py-2 rounded-lg text-sm border transition-colors disabled:opacity-50",
                  inWatchlist
                    ? "bg-yellow-500/15 border-yellow-500/40 text-yellow-400"
                    : "bg-gray-800 border-gray-700 text-gray-300 hover:text-white"
                )}
              >
                {inWatchlist ? "★ Watching" : "☆ Watch"}
              </button>
            </div>
          </div>

          {result.data_source === "stale" && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
              No live market data was found for {result.symbol}, so the figures below are simulated.
              Check the ticker, or try again later if the data feed is down.
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <EngineCard
              title="Advanced AI Momentum"
              accent="text-green-400"
              signal={adv?.signal}
              score={adv ? `${(adv.composite_score * 100).toFixed(1)}` : undefined}
            >
              {adv && (
                <>
                  <Stat label="ROC 5d / 20d / 60d">
                    <Pct value={adv.momentum.roc_5d} /> / <Pct value={adv.momentum.roc_20d} /> /{" "}
                    <Pct value={adv.momentum.roc_60d} />
                  </Stat>
                  <Stat label="RSI (14)">{adv.technicals.rsi_14.toFixed(1)}</Stat>
                  <Stat label="ADX">{adv.technicals.adx.toFixed(1)}</Stat>
                  <Stat label="MACD histogram">
                    <span className={getValueColor(adv.technicals.macd_histogram)}>
                      {adv.technicals.macd_histogram.toFixed(3)}
                    </span>
                  </Stat>
                  <Stat label="Volume ratio">{adv.volume.ratio.toFixed(2)}×</Stat>
                  <Stat label="AI prediction">
                    <span className={getValueColor(adv.ai_prediction.score)}>
                      {adv.ai_prediction.score.toFixed(3)}
                    </span>{" "}
                    <span className="text-gray-500">({(adv.ai_prediction.confidence * 100).toFixed(0)}% conf)</span>
                  </Stat>
                </>
              )}
            </EngineCard>

            <EngineCard
              title="Max Risk Momentum"
              accent="text-red-400"
              signal={mr?.signal as EngineSignal | undefined}
              score={mr ? mr.max_risk_score.toFixed(2) : undefined}
            >
              {mr && (
                <>
                  <Stat label="1W / 1M / 3M">
                    <Pct value={mr.r1w} /> / <Pct value={mr.r1m} /> / <Pct value={mr.return_3m} />
                  </Stat>
                  <Stat label="6M / 12M">
                    <Pct value={mr.return_6m} /> / <Pct value={mr.return_12m} />
                  </Stat>
                  <Stat label="RS vs SPY (3M)"><Pct value={mr.rs3m} /></Stat>
                  <Stat label="Turbo score">{mr.turbo_score.toFixed(2)}</Stat>
                  <Stat label="20-day high">{mr.is_20d_high ? "Yes" : "No"}</Stat>
                  <Stat label="vs 50DMA / stop">
                    <span className={mr.below_50dma ? "text-red-400" : "text-green-400"}>
                      {mr.below_50dma ? "Below" : "Above"}
                    </span>{" "}
                    <span className="text-gray-500">/ {formatCurrency(mr.stop_price)}</span>
                  </Stat>
                </>
              )}
            </EngineCard>

            <EngineCard
              title="Institutional Momentum"
              accent="text-indigo-400"
              signal={inst?.signal as EngineSignal | undefined}
              score={inst ? inst.vol_adjusted_score.toFixed(2) : undefined}
            >
              {inst && (
                <>
                  <Stat label="R(12-1)"><Pct value={inst.r12_skip1} /></Stat>
                  <Stat label="R(6-1) / R(3-1)">
                    <Pct value={inst.r6_skip1} /> / <Pct value={inst.r3_skip1} />
                  </Stat>
                  <Stat label="Volatility (ann.)">{inst.volatility.toFixed(1)}%</Stat>
                  <Stat label="Return / vol">{inst.risk_adj_return.toFixed(2)}</Stat>
                  <Stat label="vs 200DMA"><Pct value={inst.distance_to_200dma} /></Stat>
                  <Stat label="Liquidity ≥ $50M/day">
                    <span className={inst.passes_liquidity ? "text-green-400" : "text-red-400"}>
                      {inst.passes_liquidity ? "Pass" : "Fail"}
                    </span>
                  </Stat>
                </>
              )}
            </EngineCard>
          </div>
        </div>
      )}
    </div>
  );
}
