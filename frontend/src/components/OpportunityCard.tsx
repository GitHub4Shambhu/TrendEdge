/**
 * TrendEdge Frontend - Opportunity Card Component
 *
 * Displays a single trading opportunity with momentum data.
 * Features: mini sparkline, momentum bar, visual indicators
 */

import { TopOpportunity } from "@/lib/api";
import {
  formatCurrency,
  formatPercent,
  formatScore,
  getSignalStyle,
  getRiskColor,
  getValueColor,
} from "@/lib/utils";

interface OpportunityCardProps {
  opportunity: TopOpportunity;
}

// Mini sparkline component showing price trend
function MiniSparkline({ trend }: { trend: "up" | "down" | "neutral" }) {
  const points = trend === "up" 
    ? "0,20 8,18 16,15 24,17 32,12 40,14 48,8 56,10 64,4"
    : trend === "down"
    ? "0,4 8,6 16,10 24,8 32,14 40,12 48,18 56,16 64,20"
    : "0,12 8,10 16,14 24,12 32,13 40,11 48,12 56,13 64,12";
  
  const color = trend === "up" ? "#10B981" : trend === "down" ? "#EF4444" : "#6B7280";
  
  return (
    <svg width="64" height="24" className="opacity-80">
      <defs>
        <linearGradient id={`sparkGrad-${trend}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polygon
        points={`0,24 ${points} 64,24`}
        fill={`url(#sparkGrad-${trend})`}
      />
    </svg>
  );
}

// Momentum progress bar
function MomentumBar({ score }: { score: number }) {
  // Score ranges from -1 to 1, convert to percentage (0-100)
  const percentage = ((score + 1) / 2) * 100;
  const isPositive = score >= 0;
  
  return (
    <div className="relative h-2 bg-gray-800 rounded-full overflow-hidden">
      {/* Center line */}
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-600" />
      
      {/* Momentum fill */}
      <div
        className={`absolute top-0 bottom-0 transition-all duration-500 ${
          isPositive ? "bg-gradient-to-r from-gray-600 to-green-500" : "bg-gradient-to-l from-gray-600 to-red-500"
        }`}
        style={{
          left: isPositive ? "50%" : `${percentage}%`,
          width: isPositive ? `${percentage - 50}%` : `${50 - percentage}%`,
        }}
      />
    </div>
  );
}

// Confidence ring indicator
function ConfidenceRing({ confidence }: { confidence: number }) {
  const circumference = 2 * Math.PI * 18;
  const filled = circumference * confidence;
  
  return (
    <div className="relative w-14 h-14">
      <svg className="w-14 h-14 -rotate-90">
        <circle
          cx="28"
          cy="28"
          r="18"
          stroke="#1F2937"
          strokeWidth="4"
          fill="none"
        />
        <circle
          cx="28"
          cy="28"
          r="18"
          stroke={confidence > 0.7 ? "#10B981" : confidence > 0.5 ? "#F59E0B" : "#EF4444"}
          strokeWidth="4"
          fill="none"
          strokeDasharray={`${filled} ${circumference}`}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold text-white">
          {(confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

function formatMarketCap(value: number | null | undefined): string {
  if (value == null) return "";
  if (value >= 1_000_000_000_000) return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

export function OpportunityCard({ opportunity }: OpportunityCardProps) {
  const { momentum, rank, reason, risk_level, target_price, stop_loss, market_cap } = opportunity;
  const signalStyle = getSignalStyle(momentum.signal);
  const trend = momentum.price_change_pct > 0.5 ? "up" : momentum.price_change_pct < -0.5 ? "down" : "neutral";

  return (
    <div className="bg-gradient-to-br from-gray-900 to-gray-950 border border-gray-800 rounded-xl p-5 hover:border-gray-600 hover:shadow-lg hover:shadow-black/20 transition-all duration-300 group">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {/* Rank badge */}
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-lg ${
            rank === 1 ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30" :
            rank === 2 ? "bg-gray-400/20 text-gray-300 border border-gray-400/30" :
            rank === 3 ? "bg-orange-500/20 text-orange-400 border border-orange-500/30" :
            "bg-gray-800 text-gray-400"
          }`}>
            {rank}
          </div>
          <div>
            <h3 className="text-xl font-bold text-white group-hover:text-blue-400 transition-colors">
              {momentum.symbol}
              {market_cap != null && (
                <span className="text-xs font-bold text-gray-400 ml-1.5">
                  ({formatMarketCap(market_cap)})
                </span>
              )}
            </h3>
            <p className="text-xs text-gray-500 uppercase tracking-wider">{momentum.asset_type}</p>
          </div>
        </div>
        
        {/* Signal badge with glow effect */}
        <div className="relative">
          <span
            className={`px-3 py-1.5 rounded-lg text-sm font-bold uppercase ${signalStyle.bg} ${signalStyle.text} ${signalStyle.border} border backdrop-blur-sm`}
          >
            {momentum.signal}
          </span>
          {momentum.signal === "buy" && (
            <div className="absolute inset-0 rounded-lg bg-green-500/20 blur-md -z-10" />
          )}
        </div>
      </div>

      {/* Price section with sparkline */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-800">
        <div>
          <p className="text-3xl font-bold text-white">
            {formatCurrency(momentum.price)}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-sm font-semibold px-2 py-0.5 rounded ${
              momentum.price_change_pct >= 0 ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
            }`}>
              {formatPercent(momentum.price_change_pct)}
            </span>
            {momentum.volume_ratio > 1.3 && (
              <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 flex items-center gap-1">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zm6-4a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zm6-3a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
                </svg>
                High Vol
              </span>
            )}
          </div>
        </div>
        <MiniSparkline trend={trend} />
      </div>

      {/* Momentum Score with visual bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400 uppercase tracking-wider">Momentum Score</span>
          <span className={`text-lg font-bold ${getValueColor(momentum.score)}`}>
            {formatScore(momentum.score)}
          </span>
        </div>
        <MomentumBar score={momentum.score} />
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          {/* Volume */}
          <div className="text-center">
            <p className="text-xs text-gray-500 mb-1">Volume</p>
            <p className={`text-sm font-semibold ${momentum.volume_ratio > 1.2 ? "text-blue-400" : "text-gray-300"}`}>
              {momentum.volume_ratio.toFixed(1)}x
            </p>
          </div>
          
          {/* Risk */}
          <div className="text-center">
            <p className="text-xs text-gray-500 mb-1">Risk</p>
            <p className={`text-sm font-semibold capitalize ${getRiskColor(risk_level)}`}>
              {risk_level}
            </p>
          </div>
          
          {/* Sentiment */}
          {momentum.sentiment_score !== null && (
            <div className="text-center">
              <p className="text-xs text-gray-500 mb-1">Sentiment</p>
              <p className={`text-sm font-semibold ${momentum.sentiment_score > 0 ? "text-green-400" : momentum.sentiment_score < 0 ? "text-red-400" : "text-gray-400"}`}>
                {momentum.sentiment_score > 0 ? "+" : ""}{(momentum.sentiment_score * 100).toFixed(0)}
              </p>
            </div>
          )}
        </div>
        
        {/* Confidence ring */}
        <ConfidenceRing confidence={momentum.confidence} />
      </div>

      {/* Targets */}
      {(target_price || stop_loss) && (
        <div className="flex gap-3 mb-4 p-3 bg-gray-800/50 rounded-lg">
          {target_price && (
            <div className="flex-1 text-center">
              <p className="text-xs text-gray-500 mb-1">Target</p>
              <p className="text-sm font-semibold text-green-400">{formatCurrency(target_price)}</p>
              <p className="text-xs text-green-400/60">
                +{(((target_price - momentum.price) / momentum.price) * 100).toFixed(1)}%
              </p>
            </div>
          )}
          {target_price && stop_loss && <div className="w-px bg-gray-700" />}
          {stop_loss && (
            <div className="flex-1 text-center">
              <p className="text-xs text-gray-500 mb-1">Stop Loss</p>
              <p className="text-sm font-semibold text-red-400">{formatCurrency(stop_loss)}</p>
              <p className="text-xs text-red-400/60">
                {(((stop_loss - momentum.price) / momentum.price) * 100).toFixed(1)}%
              </p>
            </div>
          )}
        </div>
      )}

      {/* Reason */}
      <div className="flex items-start gap-2 pt-3 border-t border-gray-800">
        <svg className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-gray-400 leading-relaxed">
          {reason}
        </p>
      </div>
    </div>
  );
}
