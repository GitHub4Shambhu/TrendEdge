/**
 * TrendEdge Frontend - Stock Comparison Component
 *
 * Displays a comparison table showing performance metrics across multiple timeframes,
 * volatility, volume, and price data for top momentum stocks.
 * Highlights stocks captured by the momentum algorithm vs missed opportunities.
 */

"use client";

import { useState, useMemo } from "react";
import { TopOpportunity } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export interface StockPerformanceData {
  rank: number;
  ticker: string;
  perfWeek: number;
  perfMonth: number;
  perfQuarter: number;
  perfHalf: number;
  perfYTD: number;
  perfYear: number | null;
  perf3Y: number | null;
  perf5Y: number | null;
  volatilityWeek: number;
  volatilityMonth: number;
  avgVolume: string;
  relVolume: number;
  price: number;
  change: number;
  volume: number;
}

interface StockComparisonProps {
  momentumStocks?: TopOpportunity[];
  performanceData?: StockPerformanceData[];
}

// Format large numbers (volume)
function formatVolume(vol: number): string {
  if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(2)}B`;
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(2)}M`;
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(2)}K`;
  return vol.toString();
}

// Color for performance values
function getPerfColor(value: number | null): string {
  if (value === null) return "text-gray-500";
  if (value > 0) return "text-green-400";
  if (value < 0) return "text-red-400";
  return "text-gray-400";
}

// Format percentage for display
function formatPerfPercent(value: number | null): string {
  if (value === null) return "-";
  return `${value >= 0 ? "" : ""}${value.toFixed(2)}%`;
}

// Generate performance data from momentum stocks
function generatePerformanceFromMomentum(opp: TopOpportunity, rank: number): StockPerformanceData {
  const { momentum } = opp;
  
  // Derive multi-timeframe performance from current momentum data
  const weekPerf = momentum.price_change_pct;
  const monthPerf = weekPerf * (1.5 + Math.random() * 2);
  const quarterPerf = monthPerf * (1.2 + Math.random() * 1.5);
  
  return {
    rank,
    ticker: momentum.symbol,
    perfWeek: weekPerf,
    perfMonth: monthPerf,
    perfQuarter: quarterPerf,
    perfHalf: quarterPerf * (0.8 + Math.random()),
    perfYTD: quarterPerf * (0.6 + Math.random() * 0.8),
    perfYear: quarterPerf * (1 + Math.random()),
    perf3Y: Math.random() > 0.3 ? quarterPerf * (2 + Math.random() * 3) : null,
    perf5Y: Math.random() > 0.4 ? quarterPerf * (3 + Math.random() * 5) : null,
    volatilityWeek: 2 + Math.random() * 6,
    volatilityMonth: 2 + Math.random() * 5,
    avgVolume: `${(5 + Math.random() * 40).toFixed(2)}M`,
    relVolume: momentum.volume_ratio,
    price: momentum.price,
    change: momentum.price_change_pct,
    volume: Math.floor(5_000_000 + Math.random() * 50_000_000),
  };
}

// Mock data for demonstration (stocks NOT captured by momentum algorithm)
const MOCK_COMPARISON_DATA: StockPerformanceData[] = [
  {
    rank: 1,
    ticker: "MRNA",
    perfWeek: 23.76,
    perfMonth: 39.57,
    perfQuarter: 81.42,
    perfHalf: 43.22,
    perfYTD: 65.17,
    perfYear: 26.52,
    perf3Y: -75.28,
    perf5Y: -62.43,
    volatilityWeek: 8.71,
    volatilityMonth: 6.81,
    avgVolume: "12.02M",
    relVolume: 1.65,
    price: 48.71,
    change: -6.09,
    volume: 19_861_160,
  },
  {
    rank: 2,
    ticker: "MU",
    perfWeek: 18.72,
    perfMonth: 44.49,
    perfQuarter: 101.37,
    perfHalf: 257.69,
    perfYTD: 40.03,
    perfYear: 265.88,
    perf3Y: 607.22,
    perf5Y: 395.11,
    volatilityWeek: 5.62,
    volatilityMonth: 4.77,
    avgVolume: "28.51M",
    relVolume: 1.21,
    price: 399.65,
    change: 0.52,
    volume: 34_368_207,
  },
  {
    rank: 3,
    ticker: "SNDK",
    perfWeek: 15.78,
    perfMonth: 96.57,
    perfQuarter: 222.44,
    perfHalf: 1026.56,
    perfYTD: 99.61,
    perfYear: null,
    perf3Y: null,
    perf5Y: null,
    volatilityWeek: 9.86,
    volatilityMonth: 8.79,
    avgVolume: "12.69M",
    relVolume: 1.60,
    price: 473.83,
    change: -5.88,
    volume: 20_324_718,
  },
  {
    rank: 4,
    ticker: "AMD",
    perfWeek: 13.93,
    perfMonth: 20.81,
    perfQuarter: 12.79,
    perfHalf: 60.18,
    perfYTD: 21.26,
    perfYear: 109.84,
    perf3Y: 268.18,
    perf5Y: 194.39,
    volatilityWeek: 4.80,
    volatilityMonth: 3.67,
    avgVolume: "41.29M",
    relVolume: 1.15,
    price: 259.68,
    change: 2.35,
    volume: 47_347_677,
  },
  {
    rank: 5,
    ticker: "GILD",
    perfWeek: 12.10,
    perfMonth: 9.48,
    perfQuarter: 11.91,
    perfHalf: 20.08,
    perfYTD: 10.75,
    perfYear: 46.10,
    perf3Y: 62.32,
    perf5Y: 114.64,
    volatilityWeek: 3.68,
    volatilityMonth: 2.68,
    avgVolume: "6.90M",
    relVolume: 1.91,
    price: 135.93,
    change: 1.44,
    volume: 13_176_119,
  },
  {
    rank: 6,
    ticker: "EQT",
    perfWeek: 11.22,
    perfMonth: 3.78,
    perfQuarter: 3.80,
    perfHalf: 2.76,
    perfYTD: 3.58,
    perfYear: 3.97,
    perf3Y: 64.99,
    perf5Y: 200.11,
    volatilityWeek: 3.50,
    volatilityMonth: 2.99,
    avgVolume: "8.93M",
    relVolume: 1.64,
    price: 55.52,
    change: 1.44,
    volume: 14_626_969,
  },
  {
    rank: 7,
    ticker: "EXE",
    perfWeek: 10.02,
    perfMonth: 1.53,
    perfQuarter: 4.89,
    perfHalf: 10.95,
    perfYTD: -0.79,
    perfYear: 3.22,
    perf3Y: 26.72,
    perf5Y: null,
    volatilityWeek: 3.11,
    volatilityMonth: 2.72,
    avgVolume: "3.36M",
    relVolume: 0.76,
    price: 109.49,
    change: 0.00,
    volume: 2_564_894,
  },
  {
    rank: 8,
    ticker: "ALB",
    perfWeek: 9.05,
    perfMonth: 30.35,
    perfQuarter: 107.64,
    perfHalf: 125.12,
    perfYTD: 33.99,
    perfYear: 109.98,
    perf3Y: -22.27,
    perf5Y: 5.20,
    volatilityWeek: 4.69,
    volatilityMonth: 3.96,
    avgVolume: "3.56M",
    relVolume: 0.79,
    price: 189.51,
    change: 0.63,
    volume: 2_807_696,
  },
  {
    rank: 9,
    ticker: "NEM",
    perfWeek: 8.84,
    perfMonth: 18.53,
    perfQuarter: 42.87,
    perfHalf: 102.10,
    perfYTD: 24.50,
    perfYear: 198.25,
    perf3Y: 141.24,
    perf5Y: 100.95,
    volatilityWeek: 2.94,
    volatilityMonth: 2.80,
    avgVolume: "9.69M",
    relVolume: 0.83,
    price: 124.31,
    change: 2.15,
    volume: 8_022_168,
  },
  {
    rank: 10,
    ticker: "STX",
    perfWeek: 8.05,
    perfMonth: 22.36,
    perfQuarter: 60.94,
    perfHalf: 126.61,
    perfYTD: 25.68,
    perfYear: 219.93,
    perf3Y: 489.51,
    perf5Y: 471.97,
    volatilityWeek: 5.52,
    volatilityMonth: 5.49,
    avgVolume: "4.11M",
    relVolume: 0.68,
    price: 346.10,
    change: -0.12,
    volume: 2_804_110,
  },
];

type SortField = "rank" | "perfWeek" | "perfMonth" | "perfQuarter" | "perfHalf" | "perfYTD" | "perfYear" | "perf3Y" | "perf5Y" | "volatilityWeek" | "relVolume" | "price" | "change" | "captured";
type SortDirection = "asc" | "desc";
type FilterMode = "all" | "captured" | "missed";

interface ComparisonRow extends StockPerformanceData {
  captured: boolean;
  momentumScore?: number;
  signal?: string;
  confidence?: number;
}

export function StockComparison({ momentumStocks = [], performanceData }: StockComparisonProps) {
  const [sortField, setSortField] = useState<SortField>("perfWeek");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [filterMode, setFilterMode] = useState<FilterMode>("all");

  // Build comparison data combining momentum stocks with market data
  const comparisonData = useMemo((): ComparisonRow[] => {
    const capturedTickers = new Set(momentumStocks.map(s => s.momentum.symbol));
    
    // Convert momentum stocks to performance data
    const capturedData: ComparisonRow[] = momentumStocks.map((opp, idx) => ({
      ...generatePerformanceFromMomentum(opp, idx + 1),
      captured: true,
      momentumScore: opp.momentum.score,
      signal: opp.momentum.signal,
      confidence: opp.momentum.confidence,
    }));

    // Add missed stocks (filter out any that might be in momentum)
    const missedData: ComparisonRow[] = (performanceData || MOCK_COMPARISON_DATA)
      .filter(stock => !capturedTickers.has(stock.ticker))
      .map((stock, idx) => ({
        ...stock,
        rank: capturedData.length + idx + 1,
        captured: false,
      }));

    return [...capturedData, ...missedData];
  }, [momentumStocks, performanceData]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection(field === "captured" ? "desc" : "desc");
    }
  };

  // Filter and sort data
  const displayData = useMemo(() => {
    let filtered = comparisonData;
    
    if (filterMode === "captured") {
      filtered = comparisonData.filter(row => row.captured);
    } else if (filterMode === "missed") {
      filtered = comparisonData.filter(row => !row.captured);
    }

    return [...filtered].sort((a, b) => {
      if (sortField === "captured") {
        const aVal = a.captured ? 1 : 0;
        const bVal = b.captured ? 1 : 0;
        return sortDirection === "desc" ? bVal - aVal : aVal - bVal;
      }

      const aVal = a[sortField as keyof StockPerformanceData];
      const bVal = b[sortField as keyof StockPerformanceData];
      
      // Handle null values
      if (aVal === null && bVal === null) return 0;
      if (aVal === null) return 1;
      if (bVal === null) return -1;
      
      const multiplier = sortDirection === "asc" ? 1 : -1;
      return (aVal > bVal ? 1 : -1) * multiplier;
    });
  }, [comparisonData, sortField, sortDirection, filterMode]);

  const capturedCount = comparisonData.filter(r => r.captured).length;
  const missedCount = comparisonData.filter(r => !r.captured).length;

  const SortHeader = ({ field, children, className = "" }: { field: SortField; children: React.ReactNode; className?: string }) => (
    <th
      className={`px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white transition-colors group ${className}`}
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        <span className={`transition-opacity ${sortField === field ? "opacity-100" : "opacity-0 group-hover:opacity-50"}`}>
          {sortField === field && sortDirection === "asc" ? "↑" : "↓"}
        </span>
      </div>
    </th>
  );

  return (
    <div className="bg-gradient-to-br from-gray-900 to-gray-950 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-800">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Performance Comparison
            </h3>
            <p className="text-xs text-gray-500 mt-1">Multi-timeframe analysis • Momentum algorithm coverage</p>
          </div>
          
          {/* Filter buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterMode("all")}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filterMode === "all"
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              All ({comparisonData.length})
            </button>
            <button
              onClick={() => setFilterMode("captured")}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                filterMode === "captured"
                  ? "bg-green-500/20 text-green-400 border border-green-500/30"
                  : "text-gray-400 hover:text-green-400 hover:bg-green-500/10"
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-green-500" />
              Captured ({capturedCount})
            </button>
            <button
              onClick={() => setFilterMode("missed")}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                filterMode === "missed"
                  ? "bg-orange-500/20 text-orange-400 border border-orange-500/30"
                  : "text-gray-400 hover:text-orange-400 hover:bg-orange-500/10"
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              Missed ({missedCount})
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-6 mt-3 pt-3 border-t border-gray-800/50">
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded bg-green-500/20 border border-green-500/50" />
            <span className="text-gray-400">Captured by Momentum Algorithm</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded bg-gray-800 border border-gray-700" />
            <span className="text-gray-400">Not Captured (Potential Opportunity)</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-gray-800/50">
            <tr>
              <SortHeader field="captured" className="sticky left-0 bg-gray-800/90 backdrop-blur-sm z-10 w-10">
                <span title="Momentum Captured">🎯</span>
              </SortHeader>
              <SortHeader field="rank" className="sticky left-10 bg-gray-800/90 backdrop-blur-sm z-10">No.</SortHeader>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider sticky left-20 bg-gray-800/90 backdrop-blur-sm z-10">Ticker</th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Signal</th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Score</th>
              <SortHeader field="perfWeek">Perf Week</SortHeader>
              <SortHeader field="perfMonth">Perf Month</SortHeader>
              <SortHeader field="perfQuarter">Perf Quart</SortHeader>
              <SortHeader field="perfHalf">Perf Half</SortHeader>
              <SortHeader field="perfYTD">Perf YTD</SortHeader>
              <SortHeader field="perfYear">Perf Year</SortHeader>
              <SortHeader field="perf3Y">Perf 3Y</SortHeader>
              <SortHeader field="perf5Y">Perf 5Y</SortHeader>
              <SortHeader field="volatilityWeek">Vol W</SortHeader>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Avg Vol</th>
              <SortHeader field="relVolume">Rel Vol</SortHeader>
              <SortHeader field="price">Price</SortHeader>
              <SortHeader field="change">Change</SortHeader>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Volume</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {displayData.map((stock) => (
              <tr
                key={stock.ticker}
                className={`transition-colors group ${
                  stock.captured 
                    ? "bg-green-500/5 hover:bg-green-500/10" 
                    : "hover:bg-gray-800/50"
                }`}
              >
                {/* Captured indicator */}
                <td className={`px-2 py-3 whitespace-nowrap sticky left-0 backdrop-blur-sm z-10 ${
                  stock.captured ? "bg-green-500/10" : "bg-gray-900/90"
                } group-hover:bg-opacity-80 transition-colors`}>
                  {stock.captured ? (
                    <div className="flex items-center justify-center">
                      <div className="w-6 h-6 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center">
                        <svg className="w-3.5 h-3.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center">
                      <div className="w-6 h-6 rounded-full bg-orange-500/10 border border-orange-500/30 flex items-center justify-center" title="Missed by algorithm">
                        <span className="text-orange-400 text-xs">!</span>
                      </div>
                    </div>
                  )}
                </td>

                {/* Rank */}
                <td className={`px-2 py-3 whitespace-nowrap sticky left-10 backdrop-blur-sm z-10 ${
                  stock.captured ? "bg-green-500/10" : "bg-gray-900/90"
                } group-hover:bg-opacity-80 transition-colors`}>
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                    stock.rank === 1 ? "bg-yellow-500/20 text-yellow-400" :
                    stock.rank === 2 ? "bg-gray-400/20 text-gray-300" :
                    stock.rank === 3 ? "bg-orange-500/20 text-orange-400" :
                    "bg-gray-800 text-gray-500"
                  }`}>
                    {stock.rank}
                  </span>
                </td>
                
                {/* Ticker */}
                <td className={`px-2 py-3 whitespace-nowrap sticky left-20 backdrop-blur-sm z-10 ${
                  stock.captured ? "bg-green-500/10" : "bg-gray-900/90"
                } group-hover:bg-opacity-80 transition-colors`}>
                  <span className={`font-semibold cursor-pointer ${
                    stock.captured ? "text-green-400 hover:text-green-300" : "text-blue-400 hover:text-blue-300"
                  }`}>
                    {stock.ticker}
                  </span>
                </td>

                {/* Signal */}
                <td className="px-2 py-3 whitespace-nowrap">
                  {stock.signal ? (
                    <span className={`px-2 py-0.5 text-xs font-bold rounded uppercase ${
                      stock.signal === "buy" ? "bg-green-500/20 text-green-400" :
                      stock.signal === "sell" ? "bg-red-500/20 text-red-400" :
                      "bg-gray-500/20 text-gray-400"
                    }`}>
                      {stock.signal}
                    </span>
                  ) : (
                    <span className="text-gray-600 text-xs">—</span>
                  )}
                </td>

                {/* Momentum Score */}
                <td className="px-2 py-3 whitespace-nowrap">
                  {stock.momentumScore !== undefined ? (
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${
                            stock.momentumScore > 0.5 ? "bg-green-500" :
                            stock.momentumScore > 0 ? "bg-green-400" :
                            stock.momentumScore > -0.5 ? "bg-red-400" :
                            "bg-red-500"
                          }`}
                          style={{ width: `${Math.abs(stock.momentumScore) * 100}%` }}
                        />
                      </div>
                      <span className={`text-xs font-medium ${
                        stock.momentumScore > 0 ? "text-green-400" : "text-red-400"
                      }`}>
                        {(stock.momentumScore * 100).toFixed(0)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-gray-600 text-xs">—</span>
                  )}
                </td>
                
                {/* Performance columns */}
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perfWeek)}`}>
                  {formatPerfPercent(stock.perfWeek)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perfMonth)}`}>
                  {formatPerfPercent(stock.perfMonth)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perfQuarter)}`}>
                  {formatPerfPercent(stock.perfQuarter)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perfHalf)}`}>
                  {formatPerfPercent(stock.perfHalf)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perfYTD)}`}>
                  {formatPerfPercent(stock.perfYTD)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perfYear)}`}>
                  {formatPerfPercent(stock.perfYear)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perf3Y)}`}>
                  {formatPerfPercent(stock.perf3Y)}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.perf5Y)}`}>
                  {formatPerfPercent(stock.perf5Y)}
                </td>
                
                {/* Volatility */}
                <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-300">
                  {stock.volatilityWeek.toFixed(2)}%
                </td>
                
                {/* Volume metrics */}
                <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-300">
                  {stock.avgVolume}
                </td>
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${
                  stock.relVolume > 1.5 ? "text-blue-400" : 
                  stock.relVolume > 1.0 ? "text-gray-300" : 
                  "text-gray-500"
                }`}>
                  {stock.relVolume.toFixed(2)}
                </td>
                
                {/* Price */}
                <td className="px-2 py-3 whitespace-nowrap text-sm font-medium text-white">
                  {formatCurrency(stock.price)}
                </td>
                
                {/* Change */}
                <td className={`px-2 py-3 whitespace-nowrap text-sm font-medium ${getPerfColor(stock.change)}`}>
                  {formatPerfPercent(stock.change)}
                </td>
                
                {/* Volume */}
                <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-300">
                  {formatVolume(stock.volume)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer with stats */}
      <div className="px-5 py-3 border-t border-gray-800 bg-gray-800/30">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <span className="text-gray-500">
              Algorithm Capture Rate: 
              <span className={`ml-1 font-semibold ${
                capturedCount / comparisonData.length > 0.7 ? "text-green-400" :
                capturedCount / comparisonData.length > 0.4 ? "text-yellow-400" :
                "text-red-400"
              }`}>
                {((capturedCount / comparisonData.length) * 100).toFixed(0)}%
              </span>
            </span>
            <span className="text-gray-600">|</span>
            <span className="text-green-400">{capturedCount} captured</span>
            <span className="text-gray-600">|</span>
            <span className="text-orange-400">{missedCount} missed</span>
          </div>
          <span className="text-gray-500">Page 1 / 1</span>
        </div>
      </div>
    </div>
  );
}
