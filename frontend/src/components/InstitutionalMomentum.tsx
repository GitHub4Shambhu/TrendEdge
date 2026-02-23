/**
 * TrendEdge Frontend - Institutional Momentum Score Component
 *
 * Displays the institutional-grade momentum portfolio using the formula:
 * Score = 0.4·R(12-1) + 0.3·R(6-1) + 0.2·R(3-1) + 0.1·(R/σ × 10)
 *
 * Features: skip-month returns, volatility scaling, liquidity filters,
 * market regime overlay, quintile badges.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import {
  apiClient,
  InstitutionalPortfolioResponse,
  InstitutionalMomentumResult,
  MarketRegimeResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import DataSourceBadge from "./DataSourceBadge";

// ── Mock data for demo mode ────────────────────────────────────

const MOCK_REGIME: MarketRegimeResult = {
  regime: "BULL",
  spy_above_200dma: true,
  spy_distance_200dma: 8.5,
  market_volatility: 14.2,
  breadth: 68.0,
  description: "SPY +8.5% above 200DMA, VIX-like vol 14.2% — full exposure",
};

const MOCK_PORTFOLIO: InstitutionalMomentumResult[] = [
  {
    symbol: "NVDA",
    rank: 1,
    quintile: 1,
    price: 138.4,
    r12_skip1: 88.2,
    r6_skip1: 55.8,
    r3_skip1: 32.5,
    r1: 4.2,
    volatility: 38.5,
    risk_adj_return: 2.29,
    vol_scaled_weight: 0.145,
    raw_score: 54.63,
    vol_adjusted_score: 7.92,
    avg_dollar_volume: 320000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 40.5,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "META",
    rank: 2,
    quintile: 1,
    price: 700.25,
    r12_skip1: 72.6,
    r6_skip1: 45.3,
    r3_skip1: 28.1,
    r1: 3.8,
    volatility: 32.0,
    risk_adj_return: 2.27,
    vol_scaled_weight: 0.174,
    raw_score: 44.95,
    vol_adjusted_score: 7.82,
    avg_dollar_volume: 280000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 32.0,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "PLTR",
    rank: 3,
    quintile: 1,
    price: 120.5,
    r12_skip1: 95.4,
    r6_skip1: 62.0,
    r3_skip1: 38.5,
    r1: 6.1,
    volatility: 52.0,
    risk_adj_return: 1.83,
    vol_scaled_weight: 0.107,
    raw_score: 59.92,
    vol_adjusted_score: 6.41,
    avg_dollar_volume: 180000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 53.9,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "NFLX",
    rank: 4,
    quintile: 1,
    price: 1050.0,
    r12_skip1: 65.0,
    r6_skip1: 38.5,
    r3_skip1: 22.0,
    r1: 3.0,
    volatility: 28.5,
    risk_adj_return: 2.28,
    vol_scaled_weight: 0.196,
    raw_score: 38.01,
    vol_adjusted_score: 7.45,
    avg_dollar_volume: 210000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 34.6,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "COIN",
    rank: 5,
    quintile: 1,
    price: 270.3,
    r12_skip1: 78.0,
    r6_skip1: 48.5,
    r3_skip1: 35.0,
    r1: 5.5,
    volatility: 55.0,
    risk_adj_return: 1.42,
    vol_scaled_weight: 0.101,
    raw_score: 49.47,
    vol_adjusted_score: 5.0,
    avg_dollar_volume: 150000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 38.6,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "TSLA",
    rank: 6,
    quintile: 1,
    price: 355.0,
    r12_skip1: 70.0,
    r6_skip1: 42.0,
    r3_skip1: 25.0,
    r1: 4.0,
    volatility: 48.0,
    risk_adj_return: 1.46,
    vol_scaled_weight: 0.116,
    raw_score: 43.58,
    vol_adjusted_score: 5.06,
    avg_dollar_volume: 350000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 36.5,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "ARM",
    rank: 7,
    quintile: 2,
    price: 175.2,
    r12_skip1: 58.0,
    r6_skip1: 35.0,
    r3_skip1: 20.5,
    r1: 2.8,
    volatility: 42.0,
    risk_adj_return: 1.38,
    vol_scaled_weight: 0.133,
    raw_score: 36.38,
    vol_adjusted_score: 4.84,
    avg_dollar_volume: 95000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 36.3,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "CRWD",
    rank: 8,
    quintile: 2,
    price: 390.5,
    r12_skip1: 48.0,
    r6_skip1: 28.5,
    r3_skip1: 18.0,
    r1: 2.5,
    volatility: 35.0,
    risk_adj_return: 1.37,
    vol_scaled_weight: 0.159,
    raw_score: 30.37,
    vol_adjusted_score: 4.83,
    avg_dollar_volume: 120000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 28.0,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "AMD",
    rank: 9,
    quintile: 2,
    price: 118.3,
    r12_skip1: 25.0,
    r6_skip1: 18.0,
    r3_skip1: 10.0,
    r1: 1.5,
    volatility: 40.0,
    risk_adj_return: 0.63,
    vol_scaled_weight: 0.14,
    raw_score: 18.03,
    vol_adjusted_score: 2.52,
    avg_dollar_volume: 220000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 18.3,
    signal: "HOLD",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "AAPL",
    rank: 10,
    quintile: 2,
    price: 245.8,
    r12_skip1: 20.0,
    r6_skip1: 12.0,
    r3_skip1: 8.5,
    r1: 1.2,
    volatility: 22.0,
    risk_adj_return: 0.91,
    vol_scaled_weight: 0.253,
    raw_score: 13.49,
    vol_adjusted_score: 3.41,
    avg_dollar_volume: 450000000,
    passes_liquidity: true,
    above_200dma: true,
    distance_to_200dma: 14.3,
    signal: "HOLD",
    timestamp: new Date().toISOString(),
  },
];

const MOCK_DATA: InstitutionalPortfolioResponse = {
  portfolio: MOCK_PORTFOLIO.slice(0, 6),
  full_ranking: MOCK_PORTFOLIO,
  market_regime: MOCK_REGIME,
  breadth: 68.0,
  vol_scaling_enabled: true,
  total_scanned: 50,
};

// ── Helpers ─────────────────────────────────────────────────────

function quintileLabel(q: number): { text: string; color: string; bg: string } {
  switch (q) {
    case 1:
      return { text: "Q1 ★", color: "text-emerald-400", bg: "bg-emerald-500/20 border-emerald-500/40" };
    case 2:
      return { text: "Q2", color: "text-green-400", bg: "bg-green-500/20 border-green-500/40" };
    case 3:
      return { text: "Q3", color: "text-yellow-400", bg: "bg-yellow-500/20 border-yellow-500/40" };
    case 4:
      return { text: "Q4", color: "text-orange-400", bg: "bg-orange-500/20 border-orange-500/40" };
    case 5:
      return { text: "Q5", color: "text-red-400", bg: "bg-red-500/20 border-red-500/40" };
    default:
      return { text: "Q?", color: "text-gray-400", bg: "bg-gray-500/20 border-gray-500/40" };
  }
}

function regimeColor(regime: string): { text: string; bg: string; icon: string } {
  switch (regime) {
    case "BULL":
      return { text: "text-emerald-400", bg: "bg-emerald-500/20 border-emerald-500/40", icon: "🐂" };
    case "BEAR":
      return { text: "text-red-400", bg: "bg-red-500/20 border-red-500/40", icon: "🐻" };
    default:
      return { text: "text-yellow-400", bg: "bg-yellow-500/20 border-yellow-500/40", icon: "⚖️" };
  }
}

function returnDisplay(val: number) {
  const color = val > 0 ? "text-green-400" : val < 0 ? "text-red-400" : "text-gray-400";
  const prefix = val > 0 ? "+" : "";
  return <span className={cn("text-xs font-medium", color)}>{prefix}{val.toFixed(1)}%</span>;
}

function signalBadge(signal: string) {
  const map: Record<string, string> = {
    BUY: "bg-green-500/20 text-green-400 border-green-500/40",
    SELL: "bg-red-500/20 text-red-400 border-red-500/40",
    HOLD: "bg-gray-700/50 text-gray-400 border-gray-600/40",
  };
  return (
    <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold border", map[signal] || map.HOLD)}>
      {signal}
    </span>
  );
}

function scoreColor(score: number): string {
  if (score >= 6) return "text-emerald-400";
  if (score >= 4) return "text-green-400";
  if (score >= 2) return "text-yellow-400";
  if (score >= 0) return "text-gray-400";
  return "text-red-400";
}

function formatDollarVol(vol: number): string {
  if (vol >= 1e9) return `$${(vol / 1e9).toFixed(1)}B`;
  if (vol >= 1e6) return `$${(vol / 1e6).toFixed(0)}M`;
  return `$${vol.toLocaleString()}`;
}

// ── Score Bar ───────────────────────────────────────────────────

function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = Math.min(Math.max((score / max) * 100, 0), 100);
  const color =
    pct >= 60 ? "bg-emerald-500" : pct >= 40 ? "bg-green-500" : pct >= 20 ? "bg-yellow-500" : "bg-gray-600";
  return (
    <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
      <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

// ── Weight Bar ──────────────────────────────────────────────────

function WeightBar({ weight }: { weight: number }) {
  const pct = Math.min(weight * 100 * 4, 100); // scale: 0.25 = 100%
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400">{(weight * 100).toFixed(1)}%</span>
    </div>
  );
}

// ── Component ───────────────────────────────────────────────────

export default function InstitutionalMomentum() {
  const [data, setData] = useState<InstitutionalPortfolioResponse>(MOCK_DATA);
  const [loading, setLoading] = useState(false);
  const [volScaling, setVolScaling] = useState(true);
  const [showFullRanking, setShowFullRanking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.getInstitutionalPortfolio(10, volScaling);
      setData(result);
    } catch {
      setData(MOCK_DATA);
      setError("Using demo data — backend unavailable");
    } finally {
      setLoading(false);
    }
  }, [volScaling]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const portfolio = data.portfolio;
  const ranking = data.full_ranking;
  const regime = data.market_regime;
  const rc = regimeColor(regime.regime);

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/80 backdrop-blur overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-6 py-4 border-b border-gray-800 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            🏛️ Institutional Momentum
            {loading && (
              <span className="text-xs text-gray-500 animate-pulse">scanning…</span>
            )}
            <DataSourceBadge dataSource={data.data_source} />
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Skip-month returns · Volatility-scaled weights · Regime overlay
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Vol Scaling Toggle */}
          <button
            onClick={() => setVolScaling(!volScaling)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-medium border transition-all",
              volScaling
                ? "bg-blue-500/20 border-blue-500/40 text-blue-400"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white"
            )}
          >
            σ⁻¹ {volScaling ? "ON" : "OFF"}
          </button>
          {/* Refresh */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-400 hover:text-white disabled:opacity-50 transition-all"
          >
            {loading ? "..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* ── Formula Banner ─────────────────────────────────────── */}
      <div className="px-6 py-3 bg-gray-800/40 border-b border-gray-800">
        <p className="text-xs text-gray-500 font-mono">
          Score = 0.4·R(12-1) + 0.3·R(6-1) + 0.2·R(3-1) + 0.1·(R/σ × 10)
          {volScaling && (
            <span className="text-blue-400 ml-2">— inverse-vol weighting active</span>
          )}
        </p>
      </div>

      {/* ── Market Regime Banner ───────────────────────────────── */}
      <div className="px-6 py-3 border-b border-gray-800">
        <div className="flex flex-wrap items-center gap-4">
          {/* Regime Badge */}
          <div className={cn("flex items-center gap-2 px-3 py-1.5 rounded-lg border", rc.bg)}>
            <span className="text-lg">{rc.icon}</span>
            <span className={cn("text-sm font-bold", rc.text)}>{regime.regime}</span>
          </div>

          {/* Key stats */}
          <div className="flex flex-wrap gap-4 text-xs text-gray-400">
            <span>
              SPY{" "}
              <span className={regime.spy_above_200dma ? "text-green-400" : "text-red-400"}>
                {regime.spy_above_200dma ? "▲" : "▼"} {regime.spy_distance_200dma > 0 ? "+" : ""}
                {regime.spy_distance_200dma.toFixed(1)}%
              </span>{" "}
              vs 200DMA
            </span>
            <span>
              Vol{" "}
              <span className={regime.market_volatility < 20 ? "text-green-400" : regime.market_volatility < 30 ? "text-yellow-400" : "text-red-400"}>
                {regime.market_volatility.toFixed(1)}%
              </span>
            </span>
            <span>
              Breadth{" "}
              <span className={data.breadth > 60 ? "text-green-400" : data.breadth > 40 ? "text-yellow-400" : "text-red-400"}>
                {data.breadth.toFixed(0)}%
              </span>{" "}
              &gt; 200DMA
            </span>
            <span className="text-gray-600">
              {data.total_scanned} symbols scanned
            </span>
          </div>
        </div>
        {regime.description && (
          <p className="text-xs text-gray-500 mt-1.5">{regime.description}</p>
        )}
      </div>

      {error && (
        <div className="px-6 py-2 bg-yellow-500/10 border-b border-yellow-500/30 text-xs text-yellow-400">
          {error}
        </div>
      )}

      {/* ── Portfolio Cards ────────────────────────────────────── */}
      <div className="p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Portfolio — Top {portfolio.length} Holdings (σ⁻¹ Weighted)
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {portfolio.map((stock) => {
            const q = quintileLabel(stock.quintile);
            return (
              <div
                key={stock.symbol}
                className={cn(
                  "rounded-lg border p-4 transition-all hover:scale-[1.02]",
                  stock.signal === "BUY"
                    ? "border-green-500/30 bg-green-500/5"
                    : stock.signal === "SELL"
                      ? "border-red-500/30 bg-red-500/5"
                      : "border-gray-700 bg-gray-800/50"
                )}
              >
                {/* Top row */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 font-mono">#{stock.rank}</span>
                    <span className="text-white font-bold">{stock.symbol}</span>
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-bold border", q.bg, q.color)}>
                      {q.text}
                    </span>
                  </div>
                  {signalBadge(stock.signal)}
                </div>

                {/* Price */}
                <div className="text-lg font-semibold text-white mb-1">
                  ${stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>

                {/* Vol-adjusted Score */}
                <div className="mb-2">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-gray-500">Vol-Adj Score</span>
                    <span className={cn("font-bold", scoreColor(stock.vol_adjusted_score))}>
                      {stock.vol_adjusted_score.toFixed(2)}
                    </span>
                  </div>
                  <ScoreBar score={stock.vol_adjusted_score} />
                </div>

                {/* Skip-month returns */}
                <div className="grid grid-cols-4 gap-1 text-center mb-2">
                  <div>
                    <div className="text-[10px] text-gray-600">R12-1</div>
                    {returnDisplay(stock.r12_skip1)}
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-600">R6-1</div>
                    {returnDisplay(stock.r6_skip1)}
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-600">R3-1</div>
                    {returnDisplay(stock.r3_skip1)}
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-600">Skip</div>
                    {returnDisplay(stock.r1)}
                  </div>
                </div>

                {/* Volatility & Weight */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-700/50">
                  <span className="text-xs text-gray-500">
                    σ {stock.volatility.toFixed(0)}%
                  </span>
                  <WeightBar weight={stock.vol_scaled_weight} />
                </div>

                {/* 200DMA distance */}
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[10px] text-gray-600">200DMA</span>
                  <span className={cn(
                    "text-xs",
                    stock.above_200dma ? "text-green-400" : "text-red-400"
                  )}>
                    {stock.above_200dma ? "▲" : "▼"} {stock.distance_to_200dma > 0 ? "+" : ""}{stock.distance_to_200dma.toFixed(1)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Portfolio Rules ────────────────────────────────────── */}
      <div className="px-6 pb-4">
        <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3 flex flex-wrap gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            Inverse-vol weighted
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            Skip last month (reversal)
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
            $50M daily vol filter
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            BEAR regime → 50% exposure
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
            Rebalance monthly
          </span>
        </div>
      </div>

      {/* ── Full Ranking Table ─────────────────────────────────── */}
      <div className="px-6 pb-6">
        <button
          onClick={() => setShowFullRanking(!showFullRanking)}
          className="text-sm text-blue-400 hover:text-blue-300 mb-3 flex items-center gap-1"
        >
          {showFullRanking ? "▾ Hide" : "▸ Show"} Full Ranking ({ranking.length} stocks)
        </button>

        {showFullRanking && (
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/60 text-gray-400 text-xs uppercase">
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-center">Q</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">R12-1</th>
                  <th className="px-3 py-2 text-right">R6-1</th>
                  <th className="px-3 py-2 text-right">R3-1</th>
                  <th className="px-3 py-2 text-right">Skip</th>
                  <th className="px-3 py-2 text-right">σ</th>
                  <th className="px-3 py-2 text-right">R/σ</th>
                  <th className="px-3 py-2 text-right">Raw</th>
                  <th className="px-3 py-2 text-right">Vol-Adj</th>
                  <th className="px-3 py-2 text-right">Wt</th>
                  <th className="px-3 py-2 text-right">$ Vol</th>
                  <th className="px-3 py-2 text-center">200D</th>
                  <th className="px-3 py-2 text-center">Signal</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((stock, idx) => {
                  const q = quintileLabel(stock.quintile);
                  return (
                    <tr
                      key={stock.symbol}
                      className={cn(
                        "border-t border-gray-800/50 hover:bg-gray-800/30 transition-colors",
                        stock.quintile === 1 && "bg-emerald-500/5"
                      )}
                    >
                      <td className="px-3 py-2 text-gray-500 font-mono text-xs">{stock.rank}</td>
                      <td className="px-3 py-2 text-white font-semibold">{stock.symbol}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-bold border", q.bg, q.color)}>
                          {q.text}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-gray-300">
                        ${stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2 text-right">{returnDisplay(stock.r12_skip1)}</td>
                      <td className="px-3 py-2 text-right">{returnDisplay(stock.r6_skip1)}</td>
                      <td className="px-3 py-2 text-right">{returnDisplay(stock.r3_skip1)}</td>
                      <td className="px-3 py-2 text-right">{returnDisplay(stock.r1)}</td>
                      <td className="px-3 py-2 text-right text-gray-400">{stock.volatility.toFixed(0)}%</td>
                      <td className="px-3 py-2 text-right text-gray-300">{stock.risk_adj_return.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-gray-400">{stock.raw_score.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right">
                        <span className={cn("font-bold", scoreColor(stock.vol_adjusted_score))}>
                          {stock.vol_adjusted_score.toFixed(2)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-blue-400 text-xs">
                        {(stock.vol_scaled_weight * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right text-gray-500 text-xs">
                        {formatDollarVol(stock.avg_dollar_volume)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={cn("text-xs", stock.above_200dma ? "text-green-400" : "text-red-400")}>
                          {stock.above_200dma ? "▲" : "▼"}{Math.abs(stock.distance_to_200dma).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">{signalBadge(stock.signal)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
