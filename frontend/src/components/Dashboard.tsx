/**
 * TrendEdge Frontend - Dashboard Component
 *
 * Main dashboard displaying top opportunities and market sentiment.
 */

"use client";

import { useEffect, useState } from "react";
import { apiClient, DashboardData } from "@/lib/api";
import { OpportunityCard } from "@/components/OpportunityCard";
import { SentimentGauge } from "@/components/SentimentGauge";
import { StockComparison } from "@/components/StockComparison";
import Backtesting from "@/components/Backtesting";
import MaxRiskMomentum from "@/components/MaxRiskMomentum";
import { formatRelativeTime } from "@/lib/utils";

// Mock data for development when backend is not running
const MOCK_DATA: DashboardData = {
  top_stocks: [
    {
      rank: 1,
      momentum: {
        symbol: "NVDA",
        asset_type: "stock",
        score: 0.72,
        signal: "buy",
        confidence: 0.85,
        price: 138.40,
        price_change_pct: 3.24,
        volume_ratio: 1.8,
        sentiment_score: 0.65,
        updated_at: new Date().toISOString(),
      },
      reason: "Strong bullish momentum, high volume surge, positive social sentiment",
      risk_level: "low",
      target_price: 152.24,
      stop_loss: 131.48,
    },
    {
      rank: 2,
      momentum: {
        symbol: "META",
        asset_type: "stock",
        score: 0.58,
        signal: "buy",
        confidence: 0.78,
        price: 700.25,
        price_change_pct: 2.15,
        volume_ratio: 1.5,
        sentiment_score: 0.42,
        updated_at: new Date().toISOString(),
      },
      reason: "Moderate bullish momentum, above average volume",
      risk_level: "medium",
      target_price: 735.26,
      stop_loss: 679.24,
    },
    {
      rank: 3,
      momentum: {
        symbol: "TSLA",
        asset_type: "stock",
        score: 0.45,
        signal: "buy",
        confidence: 0.72,
        price: 355.00,
        price_change_pct: 1.87,
        volume_ratio: 1.3,
        sentiment_score: 0.38,
        updated_at: new Date().toISOString(),
      },
      reason: "Moderate bullish momentum",
      risk_level: "medium",
      target_price: 372.75,
      stop_loss: 344.35,
    },
  ],
  top_etfs: [
    {
      rank: 1,
      momentum: {
        symbol: "QQQ",
        asset_type: "etf",
        score: 0.48,
        signal: "buy",
        confidence: 0.82,
        price: 540.20,
        price_change_pct: 1.42,
        volume_ratio: 1.2,
        sentiment_score: 0.35,
        updated_at: new Date().toISOString(),
      },
      reason: "Moderate bullish momentum, tech sector strength",
      risk_level: "low",
      target_price: 567.21,
      stop_loss: 524.00,
    },
    {
      rank: 2,
      momentum: {
        symbol: "SPY",
        asset_type: "etf",
        score: 0.35,
        signal: "buy",
        confidence: 0.80,
        price: 610.50,
        price_change_pct: 0.95,
        volume_ratio: 1.1,
        sentiment_score: 0.28,
        updated_at: new Date().toISOString(),
      },
      reason: "Moderate bullish momentum, broad market strength",
      risk_level: "low",
      target_price: 641.03,
      stop_loss: 592.19,
    },
  ],
  top_options: [],
  market_sentiment: 0.35,
  last_updated: new Date().toISOString(),
};

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [useMock, setUseMock] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const dashboardData = await apiClient.getDashboard();
      setData(dashboardData);
      setUseMock(false);
    } catch (err) {
      console.warn("API unavailable, using mock data:", err);
      setData(MOCK_DATA);
      setUseMock(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-400">Loading market data...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            {/* TrendEdge Logo */}
            <div className="flex items-center gap-2">
              <svg
                className="w-10 h-10"
                viewBox="0 0 40 40"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                {/* Background circle with gradient */}
                <defs>
                  <linearGradient id="logoGradient" x1="0%" y1="100%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#10B981" />
                    <stop offset="100%" stopColor="#3B82F6" />
                  </linearGradient>
                </defs>
                <circle cx="20" cy="20" r="18" fill="url(#logoGradient)" opacity="0.15" />
                <circle cx="20" cy="20" r="18" stroke="url(#logoGradient)" strokeWidth="2" fill="none" />
                {/* Upward trending arrow/chart */}
                <path
                  d="M10 26 L16 20 L22 24 L30 12"
                  stroke="url(#logoGradient)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
                {/* Arrow head */}
                <path
                  d="M26 12 L30 12 L30 16"
                  stroke="url(#logoGradient)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
              </svg>
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 to-blue-500 bg-clip-text text-transparent">
                  TrendEdge
                </h1>
                <p className="text-xs text-gray-500 -mt-1">Momentum Intelligence</p>
              </div>
            </div>
          </div>
          <p className="text-gray-400 mt-2">
            Last updated: {formatRelativeTime(data.last_updated)}
            {useMock && (
              <span className="ml-2 text-yellow-500 text-sm">(Demo Mode)</span>
            )}
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? (
            <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          )}
          Refresh
        </button>
      </div>

      {/* Market Sentiment */}
      <SentimentGauge sentiment={data.market_sentiment} />

      {/* Top Stocks */}
      <section>
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          Top Stock Opportunities
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.top_stocks.map((opp) => (
            <OpportunityCard key={opp.momentum.symbol} opportunity={opp} />
          ))}
        </div>
      </section>

      {/* Performance Comparison Table */}
      <section>
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          Performance Comparison
        </h2>
        <StockComparison momentumStocks={data.top_stocks} />
      </section>

      {/* Max Risk Momentum Score */}
      <section>
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          Max Risk Momentum Score
        </h2>
        <MaxRiskMomentum />
      </section>

      {/* Top ETFs */}
      <section>
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          Top ETF Opportunities
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.top_etfs.map((opp) => (
            <OpportunityCard key={opp.momentum.symbol} opportunity={opp} />
          ))}
        </div>
      </section>

      {/* Options (if available) */}
      {data.top_options.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500" />
            Top Options Opportunities
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.top_options.map((opp) => (
              <OpportunityCard key={opp.momentum.symbol} opportunity={opp} />
            ))}
          </div>
        </section>
      )}

      {/* Backtesting Section */}
      <section>
        <div className="border-t border-gray-700 pt-8 mt-8">
          <Backtesting />
        </div>
      </section>
    </div>
  );
}
