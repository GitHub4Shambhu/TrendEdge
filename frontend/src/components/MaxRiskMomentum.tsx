/**
 * TrendEdge Frontend - Max Risk Momentum Score Component (v2)
 *
 * 11-factor scoring with QQQ regime filter:
 * MaxRiskMomentum = 0.18*R1W + 0.18*R1M + 0.18*R3M + 0.18*R6M + 0.08*R12M
 *                 + 0.10*RS3M + 0.06*RS6M + 0.04*RS12M
 *                 + 0.06*VExp + 0.05*BO + 0.03*VolAccel
 * Turbo: + 0.05*(R1M - R3M)
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import {
  apiClient,
  MaxRiskPortfolioResponse,
  MaxRiskScoreResult,
  MaxRiskRegimeResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import DataSourceBadge from "./DataSourceBadge";

// ── Mock regime ─────────────────────────────────────────────────
const MOCK_REGIME: MaxRiskRegimeResult = {
  risk_on: true,
  qqq_close: 540.0,
  qqq_200sma: 498.0,
  qqq_distance_pct: 8.4,
  spy_close: 610.0,
  spy_200sma: 565.0,
  description: "RISK ON -- QQQ $540 is +8.4% above 200SMA $498",
};

// ── Mock data for demo mode ────────────────────────────────────
const MOCK_MAX_RISK: MaxRiskPortfolioResponse = {
  top_picks: [
    {
      symbol: "NVDA", rank: 1, price: 138.40,
      r1w: 5.2, r1m: 12.8, return_3m: 32.5, return_6m: 55.8, return_12m: 88.2,
      rs3m: 22.0, rs6m: 38.5, rs12m: 62.0,
      vexp: 0.35, breakout_factor: 1, is_20d_high: true, vol_accel: 0.45,
      sma_50: 125.80, sma_200: 98.50, price_to_200dma: 1.405,
      max_risk_score: 52.18, turbo_score: 51.19,
      below_50dma: false, stop_price: 117.64, signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "META", rank: 2, price: 700.25,
      r1w: 3.8, r1m: 8.5, return_3m: 28.1, return_6m: 45.3, return_12m: 72.6,
      rs3m: 17.6, rs6m: 28.0, rs12m: 46.4,
      vexp: 0.18, breakout_factor: 0, is_20d_high: false, vol_accel: 0.22,
      sma_50: 655.10, sma_200: 530.40, price_to_200dma: 1.320,
      max_risk_score: 41.55, turbo_score: 40.57,
      below_50dma: false, stop_price: 595.21, signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "PLTR", rank: 3, price: 120.50,
      r1w: 7.1, r1m: 15.2, return_3m: 38.5, return_6m: 62.0, return_12m: 95.4,
      rs3m: 28.0, rs6m: 44.7, rs12m: 69.2,
      vexp: 0.52, breakout_factor: 1, is_20d_high: true, vol_accel: 0.68,
      sma_50: 105.20, sma_200: 78.30, price_to_200dma: 1.539,
      max_risk_score: 59.12, turbo_score: 57.97,
      below_50dma: false, stop_price: 102.43, signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "COIN", rank: 4, price: 270.30,
      r1w: 4.5, r1m: 10.5, return_3m: 35.0, return_6m: 48.5, return_12m: 78.0,
      rs3m: 24.5, rs6m: 31.2, rs12m: 51.8,
      vexp: 0.40, breakout_factor: 0, is_20d_high: false, vol_accel: 0.35,
      sma_50: 245.60, sma_200: 195.00, price_to_200dma: 1.386,
      max_risk_score: 46.32, turbo_score: 45.10,
      below_50dma: false, stop_price: 229.76, signal: "BUY",
      timestamp: new Date().toISOString(),
    },
    {
      symbol: "NFLX", rank: 5, price: 1050.00,
      r1w: 2.8, r1m: 6.2, return_3m: 22.0, return_6m: 38.5, return_12m: 65.0,
      rs3m: 11.5, rs6m: 21.2, rs12m: 38.8,
      vexp: 0.10, breakout_factor: 0, is_20d_high: false, vol_accel: 0.12,
      sma_50: 985.00, sma_200: 780.00, price_to_200dma: 1.346,
      max_risk_score: 32.40, turbo_score: 31.61,
      below_50dma: false, stop_price: 892.50, signal: "BUY",
      timestamp: new Date().toISOString(),
    },
  ],
  full_ranking: [],
  regime: MOCK_REGIME,
  use_turbo: false,
  scanned_at: new Date().toISOString(),
  total_scanned: 50,
};

// Populate full ranking
MOCK_MAX_RISK.full_ranking = [
  ...MOCK_MAX_RISK.top_picks,
  {
    symbol: "TSLA", rank: 6, price: 355.00,
    r1w: 6.0, r1m: 11.0, return_3m: 25.0, return_6m: 42.0, return_12m: 70.0,
    rs3m: 14.5, rs6m: 24.7, rs12m: 43.8,
    vexp: 0.30, breakout_factor: 0, is_20d_high: false, vol_accel: 0.28,
    sma_50: 320.00, sma_200: 260.00, price_to_200dma: 1.365,
    max_risk_score: 38.80, turbo_score: 38.10,
    below_50dma: false, stop_price: 301.75, signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "ARM", rank: 7, price: 175.20,
    r1w: 3.2, r1m: 7.5, return_3m: 20.5, return_6m: 35.0, return_12m: 58.0,
    rs3m: 10.0, rs6m: 17.7, rs12m: 31.8,
    vexp: 0.15, breakout_factor: 0, is_20d_high: false, vol_accel: 0.10,
    sma_50: 162.00, sma_200: 128.50, price_to_200dma: 1.363,
    max_risk_score: 28.50, turbo_score: 27.85,
    below_50dma: false, stop_price: 148.92, signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "CRWD", rank: 8, price: 390.50,
    r1w: 2.5, r1m: 5.8, return_3m: 18.0, return_6m: 28.5, return_12m: 48.0,
    rs3m: 7.5, rs6m: 11.2, rs12m: 21.8,
    vexp: 0.08, breakout_factor: 0, is_20d_high: false, vol_accel: 0.05,
    sma_50: 370.00, sma_200: 305.00, price_to_200dma: 1.280,
    max_risk_score: 22.85, turbo_score: 22.24,
    below_50dma: false, stop_price: 331.93, signal: "BUY",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "AMD", rank: 9, price: 118.30,
    r1w: 1.5, r1m: 3.0, return_3m: 10.0, return_6m: 18.0, return_12m: 25.0,
    rs3m: -0.5, rs6m: 0.7, rs12m: -1.2,
    vexp: -0.12, breakout_factor: 0, is_20d_high: false, vol_accel: -0.05,
    sma_50: 112.50, sma_200: 100.00, price_to_200dma: 1.183,
    max_risk_score: 11.20, turbo_score: 10.85,
    below_50dma: false, stop_price: 100.56, signal: "HOLD",
    timestamp: new Date().toISOString(),
  },
  {
    symbol: "AAPL", rank: 10, price: 245.80,
    r1w: 1.0, r1m: 2.5, return_3m: 8.5, return_6m: 12.0, return_12m: 20.0,
    rs3m: -2.0, rs6m: -5.3, rs12m: -6.2,
    vexp: -0.05, breakout_factor: 0, is_20d_high: false, vol_accel: -0.02,
    sma_50: 238.00, sma_200: 215.00, price_to_200dma: 1.143,
    max_risk_score: 7.85, turbo_score: 7.55,
    below_50dma: false, stop_price: 208.93, signal: "HOLD",
    timestamp: new Date().toISOString(),
  },
];

// ── Helper functions ────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 40) return "text-emerald-400";
  if (score >= 20) return "text-green-400";
  if (score >= 10) return "text-yellow-400";
  if (score >= 0) return "text-gray-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 40) return "bg-emerald-500/20";
  if (score >= 20) return "bg-green-500/20";
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
    <span className={cn("text-xs font-bold px-2 py-0.5 rounded border", styles[signal] || styles.HOLD)}>
      {signal}
    </span>
  );
}

function returnDisplay(val: number) {
  const color = val > 20 ? "text-emerald-400" : val > 0 ? "text-green-400" : val > -10 ? "text-yellow-400" : "text-red-400";
  return <span className={color}>{val > 0 ? "+" : ""}{val.toFixed(1)}%</span>;
}

function rsDisplay(val: number) {
  const color = val > 10 ? "text-cyan-400" : val > 0 ? "text-blue-400" : val > -10 ? "text-yellow-400" : "text-red-400";
  return <span className={cn("text-xs", color)}>{val > 0 ? "+" : ""}{val.toFixed(1)}</span>;
}

function vexpDisplay(val: number) {
  const pct = val * 100;
  const color = val > 0.3 ? "text-amber-400" : val > 0 ? "text-green-400" : val > -0.3 ? "text-gray-400" : "text-red-400";
  return <span className={cn("text-xs", color)}>{pct > 0 ? "+" : ""}{pct.toFixed(0)}%</span>;
}

function ScoreBar({ score, max = 80 }: { score: number; max?: number }) {
  const pct = Math.min(Math.max((score / max) * 100, 0), 100);
  const color = pct >= 60 ? "#10B981" : pct >= 30 ? "#22C55E" : pct >= 10 ? "#EAB308" : "#6B7280";
  return (
    <div className="w-full h-2 rounded-full bg-gray-700 overflow-hidden">
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

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
      {factor >= 1 ? "BO ✓" : "—"}
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
      const result = await apiClient.getMaxRiskPortfolio(10, useTurbo);
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
  const regime = data.regime;

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center text-xl">
              🔥
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                Max Risk Momentum
                {useMock && <span className="text-xs text-yellow-500 font-normal">(Demo)</span>}
                <DataSourceBadge dataSource={data.data_source} />
              </h2>
              <p className="text-xs text-gray-500">
                11-factor scoring · QQQ regime filter · {data.total_scanned} scanned
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
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
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-400 hover:text-white disabled:opacity-50 transition-all"
          >
            {loading ? "..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* ── Regime Banner ──────────────────────────────────────── */}
      <div className={cn(
        "px-6 py-3 border-b border-gray-800 flex flex-wrap items-center gap-4",
        regime.risk_on ? "bg-emerald-500/5" : "bg-red-500/10"
      )}>
        <div className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-lg border",
          regime.risk_on
            ? "bg-emerald-500/20 border-emerald-500/40"
            : "bg-red-500/20 border-red-500/40"
        )}>
          <span className="text-lg">{regime.risk_on ? "🟢" : "🔴"}</span>
          <span className={cn("text-sm font-bold", regime.risk_on ? "text-emerald-400" : "text-red-400")}>
            {regime.risk_on ? "RISK ON" : "RISK OFF"}
          </span>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-gray-400">
          <span>
            QQQ{" "}
            <span className={regime.risk_on ? "text-green-400" : "text-red-400"}>
              ${regime.qqq_close.toFixed(0)}
            </span>
            {" "}vs 200SMA{" "}
            <span className="text-gray-500">${regime.qqq_200sma.toFixed(0)}</span>
            {" "}
            <span className={regime.qqq_distance_pct > 0 ? "text-green-400" : "text-red-400"}>
              ({regime.qqq_distance_pct > 0 ? "+" : ""}{regime.qqq_distance_pct.toFixed(1)}%)
            </span>
          </span>
          <span>
            SPY <span className="text-gray-300">${regime.spy_close.toFixed(0)}</span>
            {" "}/ 200SMA <span className="text-gray-500">${regime.spy_200sma.toFixed(0)}</span>
          </span>
        </div>
        {!regime.risk_on && (
          <span className="text-xs text-red-400 font-medium">
            ⚠ Cash mode — no new positions
          </span>
        )}
      </div>

      {/* ── Formula Banner ─────────────────────────────────────── */}
      <div className="px-6 py-3 bg-gray-800/40 border-b border-gray-800">
        <p className="text-xs text-gray-500 font-mono">
          {useTurbo ? (
            <>
              Turbo = MaxRisk + 0.05·(R1M − R3M){" "}
              <span className="text-orange-400">— acceleration bonus active</span>
            </>
          ) : (
            <>
              MaxRisk = 0.18·R1W + 0.18·R1M + 0.18·R3M + 0.18·R6M + 0.08·R12M
              + 0.10·RS3M + 0.06·RS6M + 0.04·RS12M
              + 0.06·VExp + 0.05·BO + 0.03·VolAccel
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
          {picks.slice(0, 5).map((stock) => (
            <div
              key={stock.symbol}
              className={cn(
                "rounded-lg border p-4 transition-all hover:scale-[1.02]",
                !regime.risk_on ? "border-red-500/20 bg-red-500/5 opacity-60" :
                stock.signal === "BUY" ? "border-green-500/30 bg-green-500/5" :
                stock.signal === "SELL" ? "border-red-500/30 bg-red-500/5" :
                "border-gray-700 bg-gray-800/50"
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 font-mono">#{stock.rank}</span>
                  <span className="text-white font-bold">{stock.symbol}</span>
                </div>
                {signalBadge(stock.signal)}
              </div>

              <div className="text-lg font-semibold text-white mb-1">
                ${stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>

              <div className="mb-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-500">{useTurbo ? "Turbo" : "MaxRisk"}</span>
                  <span className={cn("font-bold", scoreColor(useTurbo ? stock.turbo_score : stock.max_risk_score))}>
                    {(useTurbo ? stock.turbo_score : stock.max_risk_score).toFixed(1)}
                  </span>
                </div>
                <ScoreBar score={useTurbo ? stock.turbo_score : stock.max_risk_score} />
              </div>

              {/* Returns: R1W R1M R3M */}
              <div className="grid grid-cols-3 gap-1 text-center mb-1">
                <div>
                  <div className="text-[10px] text-gray-600">1W</div>
                  <div className="text-xs font-medium">{returnDisplay(stock.r1w)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-gray-600">1M</div>
                  <div className="text-xs font-medium">{returnDisplay(stock.r1m)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-gray-600">3M</div>
                  <div className="text-xs font-medium">{returnDisplay(stock.return_3m)}</div>
                </div>
              </div>

              {/* Relative Strength */}
              <div className="flex items-center justify-between text-[10px] text-gray-600 mb-1">
                <span>RS vs SPY:</span>
                <span className="flex gap-2">
                  {rsDisplay(stock.rs3m)} / {rsDisplay(stock.rs6m)}
                </span>
              </div>

              {/* VExp + Breakout + VolAccel */}
              <div className="flex items-center justify-between pt-2 border-t border-gray-700/50">
                <BreakoutDot factor={stock.breakout_factor} isHigh={stock.is_20d_high} />
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-600">VExp</span>
                  {vexpDisplay(stock.vexp)}
                </div>
              </div>

              {stock.below_50dma && (
                <div className="mt-2 px-2 py-1 rounded bg-red-500/10 border border-red-500/30 text-xs text-red-400 text-center">
                  ⚠ Below 50DMA — EXIT
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Exit Rules ─────────────────────────────────────────── */}
      <div className="px-6 pb-4">
        <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3 flex flex-wrap gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            QQQ &lt; 200SMA → CASH
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
            Close &lt; 50DMA → EXIT
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
            −15% hard stop
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            Rebalance weekly
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
            Min $50M avg daily $ vol
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
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">R1W</th>
                  <th className="px-3 py-2 text-right">R1M</th>
                  <th className="px-3 py-2 text-right">R3M</th>
                  <th className="px-3 py-2 text-right">R6M</th>
                  <th className="px-3 py-2 text-right">R12M</th>
                  <th className="px-3 py-2 text-right">RS3</th>
                  <th className="px-3 py-2 text-right">RS6</th>
                  <th className="px-3 py-2 text-right">VExp</th>
                  <th className="px-3 py-2 text-right">BO</th>
                  <th className="px-3 py-2 text-right">{useTurbo ? "Turbo" : "MaxRisk"}</th>
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
                    <td className="px-3 py-2 text-gray-500 font-mono text-xs">{stock.rank}</td>
                    <td className="px-3 py-2 text-white font-semibold">
                      {stock.symbol}
                      {stock.is_20d_high && <span className="ml-1 text-amber-400 text-[10px]">🔥</span>}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      ${stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-3 py-2 text-right">{returnDisplay(stock.r1w)}</td>
                    <td className="px-3 py-2 text-right">{returnDisplay(stock.r1m)}</td>
                    <td className="px-3 py-2 text-right">{returnDisplay(stock.return_3m)}</td>
                    <td className="px-3 py-2 text-right">{returnDisplay(stock.return_6m)}</td>
                    <td className="px-3 py-2 text-right">{returnDisplay(stock.return_12m)}</td>
                    <td className="px-3 py-2 text-right">{rsDisplay(stock.rs3m)}</td>
                    <td className="px-3 py-2 text-right">{rsDisplay(stock.rs6m)}</td>
                    <td className="px-3 py-2 text-right">{vexpDisplay(stock.vexp)}</td>
                    <td className="px-3 py-2 text-right text-gray-400">
                      {stock.breakout_factor >= 1 ? "✓" : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className={cn(
                        "font-bold px-2 py-0.5 rounded",
                        scoreBg(useTurbo ? stock.turbo_score : stock.max_risk_score),
                        scoreColor(useTurbo ? stock.turbo_score : stock.max_risk_score)
                      )}>
                        {(useTurbo ? stock.turbo_score : stock.max_risk_score).toFixed(1)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">{signalBadge(stock.signal)}</td>
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
