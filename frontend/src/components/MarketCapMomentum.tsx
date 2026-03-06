/**
 * TrendEdge Frontend - Market Cap Momentum Component
 *
 * Tabbed UI showing momentum opportunities grouped by market cap tier:
 * Mega Cap, Large Cap, Medium Cap, Small Cap, Micro Cap.
 * Reuses OpportunityCard for individual stock display.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import {
  apiClient,
  MarketCapMomentumResponse,
  MarketCapCategory,
  TopOpportunity,
} from "@/lib/api";
import { OpportunityCard } from "@/components/OpportunityCard";
import DataSourceBadge from "./DataSourceBadge";
import { cn } from "@/lib/utils";

// ── Tab config ──────────────────────────────────────────────────

interface TabConfig {
  tier: string;
  label: string;
  shortLabel: string;
  color: string;
  activeBg: string;
  activeBorder: string;
  dot: string;
}

const TABS: TabConfig[] = [
  {
    tier: "mega",
    label: "Mega Cap",
    shortLabel: "Mega",
    color: "text-purple-400",
    activeBg: "bg-purple-500/15",
    activeBorder: "border-purple-500/40",
    dot: "bg-purple-500",
  },
  {
    tier: "large",
    label: "Large Cap",
    shortLabel: "Large",
    color: "text-blue-400",
    activeBg: "bg-blue-500/15",
    activeBorder: "border-blue-500/40",
    dot: "bg-blue-500",
  },
  {
    tier: "medium",
    label: "Medium Cap",
    shortLabel: "Mid",
    color: "text-green-400",
    activeBg: "bg-green-500/15",
    activeBorder: "border-green-500/40",
    dot: "bg-green-500",
  },
  {
    tier: "small",
    label: "Small Cap",
    shortLabel: "Small",
    color: "text-yellow-400",
    activeBg: "bg-yellow-500/15",
    activeBorder: "border-yellow-500/40",
    dot: "bg-yellow-500",
  },
  {
    tier: "micro",
    label: "Micro Cap",
    shortLabel: "Micro",
    color: "text-red-400",
    activeBg: "bg-red-500/15",
    activeBorder: "border-red-500/40",
    dot: "bg-red-500",
  },
];

// ── Mock data for demo mode ─────────────────────────────────────

function makeMockOpportunity(
  rank: number,
  symbol: string,
  price: number,
  score: number,
  changePct: number
): TopOpportunity {
  return {
    rank,
    momentum: {
      symbol,
      asset_type: "stock",
      score,
      signal: score > 0.2 ? "buy" : score < -0.2 ? "sell" : "hold",
      confidence: 0.6 + Math.random() * 0.3,
      price,
      price_change_pct: changePct,
      volume_ratio: 0.8 + Math.random() * 1.5,
      sentiment_score: null,
      updated_at: new Date().toISOString(),
    },
    reason: score > 0.3
      ? "Strong bullish momentum, high volume"
      : score > 0
      ? "Moderate bullish momentum"
      : "Neutral signals",
    risk_level: score > 0.4 ? "low" : score > 0.1 ? "medium" : "high",
    target_price: score > 0 ? Math.round(price * 1.05 * 100) / 100 : null,
    stop_loss: score > 0 ? Math.round(price * 0.97 * 100) / 100 : null,
  };
}

const MOCK_DATA: MarketCapMomentumResponse = {
  categories: [
    {
      tier: "mega",
      label: "Mega Cap (> $476.85B)",
      total_scanned: 30,
      opportunities: [
        makeMockOpportunity(1, "NVDA", 138.4, 0.72, 3.24),
        makeMockOpportunity(2, "META", 700.25, 0.58, 2.15),
        makeMockOpportunity(3, "AAPL", 245.8, 0.35, 0.95),
      ],
    },
    {
      tier: "large",
      label: "Large Cap ($81.98B — $476.85B)",
      total_scanned: 30,
      opportunities: [
        makeMockOpportunity(1, "UBER", 82.5, 0.55, 2.8),
        makeMockOpportunity(2, "ISRG", 580.0, 0.48, 1.5),
        makeMockOpportunity(3, "NOW", 960.0, 0.42, 1.2),
      ],
    },
    {
      tier: "medium",
      label: "Medium Cap ($13.73B — $81.98B)",
      total_scanned: 30,
      opportunities: [
        makeMockOpportunity(1, "CRWD", 390.5, 0.62, 3.1),
        makeMockOpportunity(2, "DDOG", 145.0, 0.5, 2.4),
        makeMockOpportunity(3, "NET", 115.0, 0.38, 1.8),
      ],
    },
    {
      tier: "small",
      label: "Small Cap ($3.50B — $13.73B)",
      total_scanned: 30,
      opportunities: [
        makeMockOpportunity(1, "SOFI", 14.5, 0.65, 4.2),
        makeMockOpportunity(2, "HOOD", 48.0, 0.52, 3.5),
        makeMockOpportunity(3, "DUOL", 310.0, 0.4, 2.0),
      ],
    },
    {
      tier: "micro",
      label: "Micro Cap (< $3.50B)",
      total_scanned: 30,
      opportunities: [
        makeMockOpportunity(1, "IONQ", 32.0, 0.7, 5.5),
        makeMockOpportunity(2, "MARA", 22.5, 0.45, 4.0),
        makeMockOpportunity(3, "RIOT", 12.8, 0.32, 3.2),
      ],
    },
  ],
  scanned_at: new Date().toISOString(),
  data_source: "live",
};

// ── Main Component ──────────────────────────────────────────────

export default function MarketCapMomentum() {
  const [data, setData] = useState<MarketCapMomentumResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [useMock, setUseMock] = useState(false);
  const [activeTab, setActiveTab] = useState("mega");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiClient.getMarketCapMomentum(5);
      setData(result);
      setUseMock(false);
    } catch {
      console.warn("[MarketCapMomentum] API unavailable, using mock data");
      setData(MOCK_DATA);
      setUseMock(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="bg-gray-900/60 rounded-xl border border-gray-800 p-8">
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  const activeCategory: MarketCapCategory | undefined = data.categories.find(
    (c) => c.tier === activeTab
  );
  const activeTabConfig = TABS.find((t) => t.tier === activeTab)!;

  return (
    <div className="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-5 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-xl">
              📊
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                Market Cap Momentum
                {useMock && (
                  <span className="text-xs text-yellow-500 font-normal">
                    (Demo)
                  </span>
                )}
                <DataSourceBadge dataSource={data.data_source} />
              </h2>
              <p className="text-xs text-gray-500">
                Advanced momentum by market cap tier · 5 tiers ·{" "}
                {data.categories.reduce((s, c) => s + c.total_scanned, 0)}{" "}
                total scanned
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={fetchData}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-400 hover:text-white disabled:opacity-50 transition-all"
        >
          {loading ? "..." : "↻ Refresh"}
        </button>
      </div>

      {/* Tabs */}
      <div className="px-6 py-3 border-b border-gray-800 flex gap-2 overflow-x-auto">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.tier;
          const cat = data.categories.find((c) => c.tier === tab.tier);
          const count = cat?.opportunities.length ?? 0;
          return (
            <button
              key={tab.tier}
              onClick={() => setActiveTab(tab.tier)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all whitespace-nowrap",
                isActive
                  ? `${tab.activeBg} ${tab.activeBorder} ${tab.color}`
                  : "bg-gray-800/50 border-gray-700/50 text-gray-400 hover:text-white hover:border-gray-600"
              )}
            >
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  isActive ? tab.dot : "bg-gray-600"
                )}
              />
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.shortLabel}</span>
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded-full",
                  isActive
                    ? `${tab.activeBg} ${tab.color}`
                    : "bg-gray-700 text-gray-500"
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Tier info bar */}
      <div className="px-6 py-3 bg-gray-800/40 border-b border-gray-800">
        <p className="text-xs text-gray-500">
          <span className={activeTabConfig.color}>
            {activeCategory?.label}
          </span>
          {" · "}
          {activeCategory?.total_scanned ?? 0} symbols scanned
          {" · "}
          Top {activeCategory?.opportunities.length ?? 0} sorted by momentum score (highest first)
        </p>
      </div>

      {/* Formula banner */}
      <div className="px-6 py-3 bg-gray-800/30 border-b border-gray-800">
        <p className="text-xs text-gray-500 font-mono">
          MomentumScore = w<sub>1</sub>·ROC(5d) + w<sub>2</sub>·ROC(10d) + w<sub>3</sub>·ROC(20d) + w<sub>4</sub>·ROC(60d)
          + TrendScore + VolumeAccel + TechnicalSignals + ML_Confidence
        </p>
        <p className="text-[10px] text-gray-600 mt-1">
          Composite of multi-timeframe rate-of-change, volume dynamics, RSI/MACD/Bollinger/ADX technicals, and ML ensemble prediction. Range: -1.0 to +1.0
        </p>
      </div>

      {/* Opportunity cards */}
      <div className="p-6">
        {activeCategory && activeCategory.opportunities.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeCategory.opportunities.map((opp) => (
              <OpportunityCard
                key={opp.momentum.symbol}
                opportunity={opp}
              />
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-32 text-gray-500">
            No opportunities found in this tier.
          </div>
        )}
      </div>
    </div>
  );
}
