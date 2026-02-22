/**
 * TrendEdge Frontend - Max Risk Momentum Score Component
 *
 * Displays the aggressive momentum portfolio using the formula:
 * MaxRiskScore = (0.35·R3) + (0.30·R6) + (0.20·R12) + (0.10·BO) + (0.05·VolAccel)
 * TurboScore  = MaxRiskScore × (Price / 200DMA)
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import {
  apiClient,
  MaxRiskPortfolioResponse,
  MaxRiskScoreResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Mock data for demo mode ────────────────────────────────────
const MOCK_MAX_RISK: MaxRiskPortfolioResponse = {
  top_picks: [
    {
      symbol: "NVDA",
      rank: 1,
      price: 138.40,
      return_3m: 32.5,
      return_6m: 55.8,
      return_12m: 88.2,
      breakout_factor: 0.91,
      is_20d_high: true,
      vol_accel: 2.35,
      sma_50: 125.80,
      sma_200: 98.50,
      price_to_200dma: 1.405,
      max_risk_score: 68.42,
      turbo_score: 96.13,
      below_50dma: false,
      stop_price: 117.64,
      signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "META",
      rank: 2,
      price: 700.25,
      return_3m: 28.1,
      return_6m: 45.3,
      return_12m: 72.6,
      breakout_factor: 0.85,
      is_20d_high: false,
      vol_accel: 1.78,
      sma_50: 655.10,
      sma_200: 530.40,
      price_to_200dma: 1.320,
      max_risk_score: 55.80,
      turbo_score: 73.66,
      below_50dma: false,
      stop_price: 595.21,
      signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "PLTR",
      rank: 3,
      price: 120.50,
      return_3m: 38.5,
      return_6m: 62.0,
      return_12m: 95.4,
      breakout_factor: 0.94,
      is_20d_high: true,
      vol_accel: 2.90,
      sma_50: 105.20,
      sma_200: 78.30,
      price_to_200dma: 1.539,
      max_risk_score: 62.18,
      turbo_score: 95.69,
      below_50dma: false,
      stop_price: 102.43,
      signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "COIN",
      rank: 4,
      price: 270.30,
      return_3m: 35.0,
      return_6m: 48.5,
      return_12m: 78.0,
      breakout_factor: 0.82,
      is_20d_high: false,
      vol_accel: 2.15,
      sma_50: 245.60,
      sma_200: 195.00,
      price_to_200dma: 1.386,
      max_risk_score: 52.40,
      turbo_score: 72.63,
      below_50dma: false,
      stop_price: 229.76,
      signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "NFLX",
      rank: 5,
      price: 1050.00,
      return_3m: 22.0,
      return_6m: 38.5,
      return_12m: 65.0,
      breakout_factor: 0.76,
      is_20d_high: false,
      vol_accel: 1.55,
      sma_50: 985.00,
      sma_200: 780.00,
      price_to_200dma: 1.346,
      max_risk_score: 42.15,
      turbo_score: 56.73,
      below_50dma: false,
      stop_price: 892.50,
      signal: "BUY",
      timestamp: new Date().toISOString(),
    },
  ],
  full_ranking: [],
  use_turbo: false,
  scanned_at: new Date().toISOString(),
  total_scanned: 50,
};

// Populate full_ranking with more mock data
MOCK_MAX_RISK.full_ranking = [
  ...MOCK_MAX_RISK.top_picks,
  {
    symbol: "ARM",
    rank: 6,
    price: 175.20,
    return_3m: 20.5,
    return_6m: 35.0,
    return_12m: 58.0,
    breakout_factor: 0.72,
    is_20d_high: false,
    vol_accel: 1.45,
    sma_50: 162.00,
    sma_200: 128.50,
    price_to_200dma: 1.363,
    max_risk_score: 38.21,
    turbo_score: 52.08,
    below_50dma: false,
    stop_price: 148.92,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "CRWD",
    rank: 7,
    price: 390.50,
    return_3m: 18.0,
    return_6m: 28.5,
    return_12m: 48.0,
    breakout_factor: 0.68,
    is_20d_high: false,
    vol_accel: 1.35,
    sma_50: 370.00,
    sma_200: 305.00,
    price_to_200dma: 1.280,
    max_risk_score: 32.40,
    turbo_score: 41.47,
    below_50dma: false,
    stop_price: 331.93,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "TSLA",
    rank: 8,
    price: 355.00,
    return_3m: 25.0,
    return_6m: 42.0,
    return_12m: 70.0,
    breakout_factor: 0.80,
    is_20d_high: false,
    vol_accel: 2.10,
    sma_50: 320.00,
    sma_200: 260.00,
    price_to_200dma: 1.365,
    max_risk_score: 44.50,
    turbo_score: 60.74,
    below_50dma: false,
    stop_price: 301.75,
    signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "AMD",
    rank: 9,
    price: 118.30,
    return_3m: 10.0,
    return_6m: 18.0,
    return_12m: 25.0,
    breakout_factor: 0.55,
    is_20d_high: false,
    vol_accel: 1.20,
    sma_50: 112.50,
    sma_200: 100.00,
    price_to_200dma: 1.183,
    max_risk_score: 18.90,
    turbo_score: 22.36,
    below_50dma: false,
    stop_price: 100.56,
    signal: "HOLD",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "AAPL",
    rank: 10,
    price: 245.80,
    return_3m: 8.5,
    return_6m: 12.0,
    return_12m: 20.0,
    breakout_factor: 0.48,
    is_20d_high: false,
    vol_accel: 1.05,
    sma_50: 238.00,
    sma_200: 215.00,
    price_to_200dma: 1.143,
    max_risk_score: 13.50,
    turbo_score: 15.43,
    below_50dma: false,
    stop_price: 208.93,
    signal: "HOLD",
    timestamp: new Date().toISOString(),
  },
];

// ── Helper functions ────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 60) return "text-emerald-400";
  if (score >= 30) return "text-green-400";
  if (score >= 10) return "text-yellow-400";
  if (score >= 0) return "text-gray-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 60) return "bg-emerald-500/20";
  if (score >= 30) return "bg-green-500/20";
  if (score >= 10) return "bg-yellow-500/20";
  if (score >= 0) return "bg-gray-500/20";
  return "bg-red-500/20";
}

function signalBadge(signal: string) {
  const styles: Record<string, string> = {
    BUY: "bg-green-500/20 text-green-400 border-green-500/30",
    SELL: "bg-red-500/20 text-red-400 border-red-500/30",
    HOLD: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  };
  return (
    <span
      className={cn(
        "text-xs font-bold px-2 py-0.5 rounded border",
        styles[signal] || styles.HOLD
      )}
    >
      {signal}
    </span>
  );
}

function returnDisplay(val: number) {
  const color =
    val > 20
      ? "text-emerald-400"
      : val > 0
        ? "text-green-400"
        : val > -10
          ? "text-yellow-400"
          : "text-red-400";
  return (
    <span className={color}>
      {val > 0 ? "+" : ""}
      {val.toFixed(1)}%
    </span>
  );
}

// ── Score bar SVG ───────────────────────────────────────────────
function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(Math.max((score / max) * 100, 0), 100);
  const color =
    pct >= 60
      ? "#10B981"
      : pct >= 30
        ? "#22C55E"
        : pct >= 10
          ? "#EAB308"
          : "#6B7280";
  return (
    <div className="w-full h-2 rounded-full bg-gray-700 overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

// ── Breakout indicator ──────────────────────────────────────────
function BreakoutDot({ factor, isHigh }: { factor: number; isHigh: boolean }) {
  if (isHigh) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-400">
        <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        20D HIGH
      </span>
    );
  }
  return (
    <span className="text-xs text-gray-400">
      {(factor * 100).toFixed(0)}%
    </span>
  );
}

// ── Main Component ──────────────────────────────────────────────

export default function MaxRiskMomentum() {
  const [data, setData] = useState<MaxRiskPortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [useTurbo, setUseTurbo] = useState(false);
  const [showFullRanking, setShowFullRanking] = useState(false);
  const [useMock, setUseMock] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiClient.getMaxRiskPortfolio(5, useTurbo);
      setData(result);
      setUseMock(false);
    } catch {
      console.warn("[MaxRisk] API unavailable, using mock data");
      setData(MOCK_MAX_RISK);
      setUseMock(true);
    } finally {
      setLoading(false);
    }
  }, [useTurbo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="bg-gray-900/60 rounded-xl border border-gray-800 p-8">
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  const picks = data.top_picks;
  const ranking = data.full_ranking;

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            {/* Fire icon */}
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center text-xl">
              🔥
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                Max Risk Momentum
                {useMock && (
                  <span className="text-xs text-yellow-500 font-normal">
                    (Demo)
                  </span>
                )}
              </h2>
              <p className="text-xs text-gray-500">
                Aggressive momentum · Top {picks.length} equal-weight picks ·{" "}
                {data.total_scanned} scanned
              </p>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {/* Turbo Toggle */}
          <button
            onClick={() => setUseTurbo(!useTurbo)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-medium border transition-all",
              useTurbo
                ? "bg-orange-500/20 border-orange-500/40 text-orange-400"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white"
            )}
          >
            ⚡ {useTurbo ? "Turbo ON" : "Turbo OFF"}
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
          {useTurbo ? (
            <>
              TurboScore = MaxRiskScore × (Price / 200DMA){" "}
              <span className="text-orange-400">— convexity bias active</span>
            </>
          ) : (
            <>
              MaxRiskScore = (0.35·R3) + (0.30·R6) + (0.20·R12) + (0.10·BO) +
              (0.05·VolAccel)
            </>
          )}
        </p>
      </div>

      {/* ── Top Picks Cards ────────────────────────────────────── */}
      <div className="p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Portfolio — Top {picks.length} Picks (Equal Weight)
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {picks.map((stock) => (
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
                  <span className="text-xs text-gray-500 font-mono">
                    #{stock.rank}
                  </span>
                  <span className="text-white font-bold">{stock.symbol}</span>
                </div>
                {signalBadge(stock.signal)}
              </div>

              {/* Price */}
              <div className="text-lg font-semibold text-white mb-1">
                ${stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>

              {/* Score */}
              <div className="mb-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-500">
                    {useTurbo ? "Turbo" : "MaxRisk"}
                  </span>
                  <span
                    className={cn(
                      "font-bold",
                      scoreColor(useTurbo ? stock.turbo_score : stock.max_risk_score)
                    )}
                  >
                    {(useTurbo ? stock.turbo_score : stock.max_risk_score).toFixed(1)}
                  </span>
                </div>
                <ScoreBar
                  score={useTurbo ? stock.turbo_score : stock.max_risk_score}
                />
              </div>

              {/* Returns row */}
              <div className="grid grid-cols-3 gap-1 text-center">
                <div>
                  <div className="text-[10px] text-gray-600">3M</div>
                  <div className="text-xs font-medium">
                    {returnDisplay(stock.return_3m)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-gray-600">6M</div>
                  <div className="text-xs font-medium">
                    {returnDisplay(stock.return_6m)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-gray-600">12M</div>
                  <div className="text-xs font-medium">
                    {returnDisplay(stock.return_12m)}
                  </div>
                </div>
              </div>

              {/* Breakout & Volume */}
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-700/50">
                <BreakoutDot
                  factor={stock.breakout_factor}
                  isHigh={stock.is_20d_high}
                />
                <span
                  className={cn(
                    "text-xs",
                    stock.vol_accel > 2
                      ? "text-amber-400"
                      : stock.vol_accel > 1.5
                        ? "text-green-400"
                        : "text-gray-500"
                  )}
                >
                  Vol {stock.vol_accel.toFixed(1)}x
                </span>
              </div>

              {/* Exit alerts */}
              {stock.below_50dma && (
                <div className="mt-2 px-2 py-1 rounded bg-red-500/10 border border-red-500/30 text-xs text-red-400 text-center">
                  ⚠ Below 50DMA — EXIT
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Exit Rules Reminder ────────────────────────────────── */}
      <div className="px-6 pb-4">
        <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3 flex flex-wrap gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            Drop out of top 10 → EXIT
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
            Close &lt; 50DMA → EXIT
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
            −15% from entry → HARD STOP
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            Rebalance weekly
          </span>
        </div>
      </div>

      {/* ── Full Ranking Table ─────────────────────────────────── */}
      <div className="px-6 pb-6">
        <button
          onClick={() => setShowFullRanking(!showFullRanking)}
          className="text-sm text-blue-400 hover:text-blue-300 mb-3 flex items-center gap-1"
        >
          {showFullRanking ? "▾ Hide" : "▸ Show"} Full Ranking (
          {ranking.length} stocks)
        </button>

        {showFullRanking && (
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/60 text-gray-400 text-xs uppercase">
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">R3</th>
                  <th className="px-3 py-2 text-right">R6</th>
                  <th className="px-3 py-2 text-right">R12</th>
                  <th className="px-3 py-2 text-right">BO</th>
                  <th className="px-3 py-2 text-right">Vol</th>
                  <th className="px-3 py-2 text-right">
                    {useTurbo ? "Turbo" : "MaxRisk"}
                  </th>
                  <th className="px-3 py-2 text-right">P/200DMA</th>
                  <th className="px-3 py-2 text-center">Signal</th>
                  <th className="px-3 py-2 text-right">Stop</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((stock, idx) => (
                  <tr
                    key={stock.symbol}
                    className={cn(
                      "border-t border-gray-800/50 hover:bg-gray-800/30 transition-colors",
                      idx < 5 && "bg-green-500/5"
                    )}
                  >
                    <td className="px-3 py-2 text-gray-500 font-mono text-xs">
                      {stock.rank}
                    </td>
                    <td className="px-3 py-2 text-white font-semibold">
                      {stock.symbol}
                      {stock.is_20d_high && (
                        <span className="ml-1 text-amber-400 text-[10px]">
                          🔥
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      ${stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {returnDisplay(stock.return_3m)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {returnDisplay(stock.return_6m)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {returnDisplay(stock.return_12m)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-400">
                      {(stock.breakout_factor * 100).toFixed(0)}%
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right",
                        stock.vol_accel > 2
                          ? "text-amber-400"
                          : stock.vol_accel > 1.5
                            ? "text-green-400"
                            : "text-gray-400"
                      )}
                    >
                      {stock.vol_accel.toFixed(1)}x
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span
                        className={cn(
                          "font-bold px-2 py-0.5 rounded",
                          scoreBg(
                            useTurbo
                              ? stock.turbo_score
                              : stock.max_risk_score
                          ),
                          scoreColor(
                            useTurbo
                              ? stock.turbo_score
                              : stock.max_risk_score
                          )
                        )}
                      >
                        {(useTurbo
                          ? stock.turbo_score
                          : stock.max_risk_score
                        ).toFixed(1)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-gray-400 text-xs">
                      {stock.price_to_200dma.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {signalBadge(stock.signal)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500 text-xs">
                      ${stock.stop_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
