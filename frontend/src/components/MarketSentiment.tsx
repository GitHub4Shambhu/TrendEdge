/**
 * TrendEdge Frontend - Market Sentiment Dashboard Component
 *
 * Single rolling W-window sentiment model with 9 metrics:
 *  1. IV-RV Spread  2. Put-Call Skew  3. Put/Call Volume
 *  4. Delta Flow     5. % Above MA     6. Advance-Decline
 *  7. Price Accel    8. VW Momentum    9. ATR Compression
 *
 * Z-score → weighted aggregation → logistic → 0-1 → regime
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import {
  apiClient,
  MarketSentimentResponse,
  SentimentMetricDetail,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Mock Data ───────────────────────────────────────────────────

const MOCK_SENTIMENT: MarketSentimentResponse = {
  final_score: 0.68,
  regime: "Risk-On",
  trend_direction: "Rising",
  trend_slope: 0.082,
  composite_raw: 0.62,
  window_size: 20,
  timestamp: new Date().toISOString(),
  metrics: [
    { name: "iv_rv_spread", raw_value: -3.2, z_score: 0.85, weight: 0.14, weighted_z: 0.119, description: "Implied vs Realized Vol spread", series: [] },
    { name: "put_call_skew", raw_value: -1.05, z_score: 0.42, weight: 0.12, weighted_z: 0.050, description: "25Δ Put-Call Skew proxy", series: [] },
    { name: "put_call_volume", raw_value: -0.45, z_score: 0.65, weight: 0.12, weighted_z: 0.078, description: "Put/Call Volume Ratio", series: [] },
    { name: "delta_flow", raw_value: 1.8, z_score: 0.72, weight: 0.10, weighted_z: 0.072, description: "Net Option Delta Flow / Avg Vol", series: [] },
    { name: "pct_above_ma", raw_value: 68.5, z_score: 0.95, weight: 0.13, weighted_z: 0.124, description: "% Stocks above 20d MA", series: [] },
    { name: "adv_dec_ratio", raw_value: 1.55, z_score: 0.58, weight: 0.12, weighted_z: 0.070, description: "Advance-Decline Ratio", series: [] },
    { name: "price_acceleration", raw_value: 2.1, z_score: 0.48, weight: 0.10, weighted_z: 0.048, description: "Price Accel (10d vs 20d)", series: [] },
    { name: "vw_momentum", raw_value: 3.5, z_score: 0.55, weight: 0.10, weighted_z: 0.055, description: "Volume-Weighted Momentum", series: [] },
    { name: "atr_compression", raw_value: 0.72, z_score: -0.20, weight: 0.07, weighted_z: -0.014, description: "ATR Compression Ratio", series: [] },
  ],
};

// ── Helpers ─────────────────────────────────────────────────────

const REGIME_CONFIG: Record<string, { color: string; bg: string; border: string; emoji: string; gradient: string }> = {
  "Fear":       { color: "text-red-400",     bg: "bg-red-500/10",     border: "border-red-500/40",     emoji: "😨", gradient: "from-red-600 to-red-400" },
  "Defensive":  { color: "text-orange-400",  bg: "bg-orange-500/10",  border: "border-orange-500/40",  emoji: "🛡️", gradient: "from-orange-600 to-orange-400" },
  "Neutral":    { color: "text-gray-400",    bg: "bg-gray-500/10",    border: "border-gray-500/40",    emoji: "😐", gradient: "from-gray-600 to-gray-400" },
  "Risk-On":    { color: "text-green-400",   bg: "bg-green-500/10",   border: "border-green-500/40",   emoji: "🚀", gradient: "from-green-600 to-green-400" },
  "Euphoria":   { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/40", emoji: "🤩", gradient: "from-emerald-500 to-cyan-400" },
};

function getRegimeConfig(regime: string) {
  return REGIME_CONFIG[regime] || REGIME_CONFIG["Neutral"];
}

function scoreColor(score: number): string {
  if (score >= 0.85) return "text-emerald-400";
  if (score >= 0.65) return "text-green-400";
  if (score >= 0.35) return "text-yellow-400";
  if (score >= 0.15) return "text-orange-400";
  return "text-red-400";
}

function zScoreColor(z: number): string {
  if (z >= 1.5)  return "bg-emerald-500";
  if (z >= 0.5)  return "bg-green-500";
  if (z >= -0.5) return "bg-gray-500";
  if (z >= -1.5) return "bg-orange-500";
  return "bg-red-500";
}

function zScoreTextColor(z: number): string {
  if (z >= 1.5)  return "text-emerald-400";
  if (z >= 0.5)  return "text-green-400";
  if (z >= -0.5) return "text-gray-400";
  if (z >= -1.5) return "text-orange-400";
  return "text-red-400";
}

function trendArrow(dir: string) {
  if (dir === "Rising")  return { symbol: "↗", color: "text-green-400", label: "Rising" };
  if (dir === "Falling") return { symbol: "↘", color: "text-red-400",   label: "Falling" };
  return                          { symbol: "→", color: "text-gray-400", label: "Flat" };
}

function metricLabel(name: string): string {
  const labels: Record<string, string> = {
    iv_rv_spread: "IV-RV Spread",
    put_call_skew: "Put/Call Skew",
    put_call_volume: "P/C Volume",
    delta_flow: "Delta Flow",
    pct_above_ma: "Breadth",
    adv_dec_ratio: "A/D Ratio",
    price_acceleration: "Price Accel",
    vw_momentum: "VW Momentum",
    atr_compression: "ATR Compress",
  };
  return labels[name] || name;
}

function metricIcon(name: string): string {
  const icons: Record<string, string> = {
    iv_rv_spread: "📊",
    put_call_skew: "⚖️",
    put_call_volume: "📉",
    delta_flow: "🌊",
    pct_above_ma: "📈",
    adv_dec_ratio: "⬆️",
    price_acceleration: "⚡",
    vw_momentum: "💪",
    atr_compression: "🔄",
  };
  return icons[name] || "📌";
}

// ── Semicircle Gauge ────────────────────────────────────────────

function SentimentGaugeSVG({ score, regime }: { score: number; regime: string }) {
  const cfg = getRegimeConfig(regime);
  const angle = -180 + score * 180; // -180 to 0
  const r = 80;
  const cx = 100;
  const cy = 95;

  // Arc path for the background
  const arcPath = (startAngle: number, endAngle: number) => {
    const s = (startAngle * Math.PI) / 180;
    const e = (endAngle * Math.PI) / 180;
    const x1 = cx + r * Math.cos(s);
    const y1 = cy + r * Math.sin(s);
    const x2 = cx + r * Math.cos(e);
    const y2 = cy + r * Math.sin(e);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  // Needle
  const needleAngle = ((angle - 90) * Math.PI) / 180;
  const needleLen = r - 15;
  const nx = cx + needleLen * Math.cos(needleAngle);
  const ny = cy + needleLen * Math.sin(needleAngle);

  return (
    <svg viewBox="0 0 200 120" className="w-full max-w-[280px] mx-auto">
      {/* Background arcs — 5 regime zones */}
      <path d={arcPath(-180, -144)} stroke="#EF4444" strokeWidth="8" fill="none" opacity="0.3" strokeLinecap="round" />
      <path d={arcPath(-144, -108)} stroke="#F97316" strokeWidth="8" fill="none" opacity="0.3" strokeLinecap="round" />
      <path d={arcPath(-108, -72)}  stroke="#6B7280" strokeWidth="8" fill="none" opacity="0.3" strokeLinecap="round" />
      <path d={arcPath(-72, -36)}   stroke="#22C55E" strokeWidth="8" fill="none" opacity="0.3" strokeLinecap="round" />
      <path d={arcPath(-36, 0)}     stroke="#10B981" strokeWidth="8" fill="none" opacity="0.3" strokeLinecap="round" />

      {/* Active arc up to score */}
      <path
        d={arcPath(-180, angle)}
        stroke="url(#gaugeGrad)"
        strokeWidth="10"
        fill="none"
        strokeLinecap="round"
      />

      <defs>
        <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#EF4444" />
          <stop offset="25%" stopColor="#F97316" />
          <stop offset="50%" stopColor="#6B7280" />
          <stop offset="75%" stopColor="#22C55E" />
          <stop offset="100%" stopColor="#10B981" />
        </linearGradient>
      </defs>

      {/* Needle */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="white" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="4" fill="white" />

      {/* Score text */}
      <text x={cx} y={cy + 2} textAnchor="middle" className="text-2xl font-bold" fill="white" fontSize="22">
        {(score * 100).toFixed(0)}
      </text>

      {/* Labels */}
      <text x="18" y="100" fill="#EF4444" fontSize="8" opacity="0.7">Fear</text>
      <text x="160" y="100" fill="#10B981" fontSize="8" opacity="0.7">Euphoria</text>
    </svg>
  );
}

// ── Z-Score Bar ─────────────────────────────────────────────────

function ZScoreBar({ z }: { z: number }) {
  // Map z-score from [-3, +3] to 0-100% position
  const pct = Math.min(Math.max(((z + 3) / 6) * 100, 2), 98);
  const midPct = 50;

  return (
    <div className="relative w-full h-2 rounded-full bg-gray-700 overflow-hidden">
      {/* Center line */}
      <div className="absolute top-0 bottom-0 w-px bg-gray-500" style={{ left: "50%" }} />
      {/* Bar from center to value */}
      {z >= 0 ? (
        <div
          className={cn("absolute top-0 bottom-0 rounded-r-full", zScoreColor(z))}
          style={{ left: `${midPct}%`, width: `${pct - midPct}%` }}
        />
      ) : (
        <div
          className={cn("absolute top-0 bottom-0 rounded-l-full", zScoreColor(z))}
          style={{ left: `${pct}%`, width: `${midPct - pct}%` }}
        />
      )}
      {/* Dot indicator */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-white border-2 border-gray-900"
        style={{ left: `${pct}%`, transform: "translate(-50%, -50%)" }}
      />
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────

export default function MarketSentiment() {
  const [data, setData] = useState<MarketSentimentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [useMock, setUseMock] = useState(false);
  const [window, setWindow] = useState(20);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiClient.getMarketSentiment(window);
      setData(result);
      setUseMock(false);
    } catch {
      console.warn("[Sentiment] API unavailable, using mock data");
      setData(MOCK_SENTIMENT);
      setUseMock(true);
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="bg-gray-900/60 rounded-xl border border-gray-800 p-8">
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  const cfg = getRegimeConfig(data.regime);
  const trend = trendArrow(data.trend_direction);

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xl">
            🧠
          </div>
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              Market Sentiment
              {useMock && <span className="text-xs text-yellow-500 font-normal">(Demo)</span>}
            </h2>
            <p className="text-xs text-gray-500">
              9 metrics · {data.window_size}-day rolling window · Z-score normalized
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Window selector */}
          <div className="flex items-center gap-1.5 bg-gray-800 rounded-lg border border-gray-700 px-2 py-1">
            <span className="text-xs text-gray-500">W:</span>
            {[10, 20, 40].map((w) => (
              <button
                key={w}
                onClick={() => setWindow(w)}
                className={cn(
                  "text-xs px-2 py-0.5 rounded transition-all",
                  window === w
                    ? "bg-blue-500/20 text-blue-400"
                    : "text-gray-500 hover:text-white"
                )}
              >
                {w}d
              </button>
            ))}
          </div>
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
      <div className={cn("px-6 py-3 border-b border-gray-800 flex flex-wrap items-center gap-4", cfg.bg)}>
        <div className={cn("flex items-center gap-2 px-3 py-1.5 rounded-lg border", cfg.bg, cfg.border)}>
          <span className="text-lg">{cfg.emoji}</span>
          <span className={cn("text-sm font-bold", cfg.color)}>{data.regime.toUpperCase()}</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>
            Score{" "}
            <span className={cn("font-bold", scoreColor(data.final_score))}>
              {(data.final_score * 100).toFixed(1)}
            </span>
          </span>
          <span className="flex items-center gap-1">
            Trend{" "}
            <span className={cn("font-bold", trend.color)}>
              {trend.symbol} {trend.label}
            </span>
          </span>
          <span>
            Slope{" "}
            <span className="text-gray-300">
              {data.trend_slope > 0 ? "+" : ""}{data.trend_slope.toFixed(4)}/day
            </span>
          </span>
        </div>
      </div>

      {/* ── Score & Gauge Row ──────────────────────────────────── */}
      <div className="px-6 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Gauge */}
        <div className="flex flex-col items-center justify-center">
          <SentimentGaugeSVG score={data.final_score} regime={data.regime} />
          <p className={cn("text-lg font-bold mt-2", cfg.color)}>
            {data.regime}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Raw composite: {data.composite_raw > 0 ? "+" : ""}{data.composite_raw.toFixed(3)}
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="lg:col-span-2">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Metric Z-Scores (within {data.window_size}-day window)
          </h3>
          <div className="space-y-2.5">
            {data.metrics.map((m) => (
              <div key={m.name} className="group">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs w-4 text-center">{metricIcon(m.name)}</span>
                  <span className="text-xs text-gray-400 w-24 shrink-0">{metricLabel(m.name)}</span>
                  <div className="flex-1">
                    <ZScoreBar z={m.z_score} />
                  </div>
                  <span className={cn("text-xs font-mono w-12 text-right", zScoreTextColor(m.z_score))}>
                    {m.z_score > 0 ? "+" : ""}{m.z_score.toFixed(2)}
                  </span>
                  <span className="text-[10px] text-gray-600 w-8 text-right">
                    {(m.weight * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Summary Stats Row ──────────────────────────────────── */}
      <div className="px-6 pb-5">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Score */}
          <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 p-3 text-center">
            <p className="text-[10px] text-gray-500 uppercase mb-1">Final Score</p>
            <p className={cn("text-2xl font-bold", scoreColor(data.final_score))}>
              {(data.final_score * 100).toFixed(1)}
            </p>
          </div>
          {/* Regime */}
          <div className={cn("rounded-lg border p-3 text-center", cfg.bg, cfg.border)}>
            <p className="text-[10px] text-gray-500 uppercase mb-1">Regime</p>
            <p className={cn("text-lg font-bold", cfg.color)}>
              {cfg.emoji} {data.regime}
            </p>
          </div>
          {/* Trend */}
          <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 p-3 text-center">
            <p className="text-[10px] text-gray-500 uppercase mb-1">Trend</p>
            <p className={cn("text-lg font-bold", trend.color)}>
              {trend.symbol} {trend.label}
            </p>
          </div>
          {/* Window */}
          <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 p-3 text-center">
            <p className="text-[10px] text-gray-500 uppercase mb-1">Window</p>
            <p className="text-lg font-bold text-gray-300">
              {data.window_size} days
            </p>
          </div>
        </div>
      </div>

      {/* ── Model Info ─────────────────────────────────────────── */}
      <div className="px-6 pb-4">
        <div className="rounded-lg bg-gray-800/40 border border-gray-700/50 px-4 py-3">
          <p className="text-xs text-gray-500 font-mono">
            Σ(wᵢ · Zᵢ) = {data.composite_raw > 0 ? "+" : ""}{data.composite_raw.toFixed(4)}
            {" → "}σ(k·x) = {data.final_score.toFixed(4)}
            {" → "}<span className={cfg.color}>{data.regime}</span>
          </p>
          <p className="text-[10px] text-gray-600 mt-1">
            All 9 metrics Z-scored within the same {data.window_size}-day rolling window · No expanding windows · No external lookback
          </p>
        </div>
      </div>
    </div>
  );
}
