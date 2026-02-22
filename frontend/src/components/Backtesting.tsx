"use client";

import { useState } from "react";

// Types
interface BacktestRequest {
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  position_size_pct: number;
  max_positions: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  momentum_buy_threshold: number;
  momentum_sell_threshold: number;
  rebalance_frequency: number;
}

interface TradeResult {
  symbol: string;
  action: string;
  entry_date: string;
  entry_price: number;
  exit_date: string | null;
  exit_price: number | null;
  shares: number;
  pnl: number;
  pnl_percent: number;
  holding_days: number;
  exit_reason: string;
}

interface BacktestResponse {
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_trade_return: number;
  avg_holding_days: number;
  benchmark_return: number;
  alpha: number;
  start_date: string;
  end_date: string;
  trading_days: number;
  trades: TradeResult[];
  equity_curve: number[];
  dates: string[];
}

interface Preset {
  name: string;
  description: string;
  config: Partial<BacktestRequest>;
}

// Utility to format numbers
const formatCurrency = (value: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatPercent = (value: number) => {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
};

// Mini chart component for equity curve
function EquityCurveChart({ data, dates }: { data: number[]; dates: string[] }) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const height = 200;
  const width = 100;

  const points = data.map((value, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  // Calculate fill path
  const fillPoints = `0,${height} ${points} ${width},${height}`;
  
  const isPositive = data[data.length - 1] >= data[0];
  const strokeColor = isPositive ? "#22c55e" : "#ef4444";
  const fillColor = isPositive ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)";

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48">
        <defs>
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon
          points={fillPoints}
          fill="url(#equityGradient)"
        />
        <polyline
          points={points}
          fill="none"
          stroke={strokeColor}
          strokeWidth="0.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>{dates[0]}</span>
        <span>{dates[dates.length - 1]}</span>
      </div>
    </div>
  );
}

// Metric card component
function MetricCard({ 
  label, 
  value, 
  subValue,
  isPositive,
  icon 
}: { 
  label: string; 
  value: string; 
  subValue?: string;
  isPositive?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
      <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
        {icon}
        {label}
      </div>
      <div className={`text-2xl font-bold ${
        isPositive === undefined 
          ? "text-white"
          : isPositive 
            ? "text-green-400" 
            : "text-red-400"
      }`}>
        {value}
      </div>
      {subValue && (
        <div className="text-xs text-gray-500 mt-1">{subValue}</div>
      )}
    </div>
  );
}

// Trade list component
function TradeList({ trades }: { trades: TradeResult[] }) {
  const [sortBy, setSortBy] = useState<"date" | "pnl" | "symbol">("date");
  const [sortAsc, setSortAsc] = useState(false);

  const sortedTrades = [...trades].sort((a, b) => {
    let comparison = 0;
    switch (sortBy) {
      case "date":
        comparison = new Date(a.entry_date).getTime() - new Date(b.entry_date).getTime();
        break;
      case "pnl":
        comparison = a.pnl - b.pnl;
        break;
      case "symbol":
        comparison = a.symbol.localeCompare(b.symbol);
        break;
    }
    return sortAsc ? comparison : -comparison;
  });

  const handleSort = (column: "date" | "pnl" | "symbol") => {
    if (sortBy === column) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(column);
      setSortAsc(false);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th 
              className="text-left py-3 px-2 cursor-pointer hover:bg-gray-700/50"
              onClick={() => handleSort("symbol")}
            >
              Symbol {sortBy === "symbol" && (sortAsc ? "↑" : "↓")}
            </th>
            <th className="text-left py-3 px-2">Action</th>
            <th 
              className="text-left py-3 px-2 cursor-pointer hover:bg-gray-700/50"
              onClick={() => handleSort("date")}
            >
              Entry {sortBy === "date" && (sortAsc ? "↑" : "↓")}
            </th>
            <th className="text-right py-3 px-2">Entry $</th>
            <th className="text-left py-3 px-2">Exit</th>
            <th className="text-right py-3 px-2">Exit $</th>
            <th className="text-right py-3 px-2">Days</th>
            <th 
              className="text-right py-3 px-2 cursor-pointer hover:bg-gray-700/50"
              onClick={() => handleSort("pnl")}
            >
              P&L {sortBy === "pnl" && (sortAsc ? "↑" : "↓")}
            </th>
            <th className="text-left py-3 px-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {sortedTrades.map((trade, idx) => (
            <tr 
              key={idx} 
              className="border-b border-gray-800 hover:bg-gray-800/50"
            >
              <td className="py-2 px-2 font-medium">{trade.symbol}</td>
              <td className="py-2 px-2">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  trade.action === "BUY" 
                    ? "bg-green-500/20 text-green-400"
                    : "bg-red-500/20 text-red-400"
                }`}>
                  {trade.action}
                </span>
              </td>
              <td className="py-2 px-2 text-gray-400">
                {new Date(trade.entry_date).toLocaleDateString()}
              </td>
              <td className="py-2 px-2 text-right">${trade.entry_price.toFixed(2)}</td>
              <td className="py-2 px-2 text-gray-400">
                {trade.exit_date ? new Date(trade.exit_date).toLocaleDateString() : "-"}
              </td>
              <td className="py-2 px-2 text-right">
                {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : "-"}
              </td>
              <td className="py-2 px-2 text-right text-gray-400">
                {trade.holding_days}
              </td>
              <td className={`py-2 px-2 text-right font-medium ${
                trade.pnl >= 0 ? "text-green-400" : "text-red-400"
              }`}>
                {formatPercent(trade.pnl_percent)}
              </td>
              <td className="py-2 px-2 text-gray-500 text-xs">{trade.exit_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Main Backtesting component
export default function Backtesting() {
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Form state
  const [config, setConfig] = useState<BacktestRequest>({
    symbols: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AMD", "TSLA"],
    start_date: "2023-01-01",
    end_date: "2024-01-01",
    initial_capital: 100000,
    position_size_pct: 0.10,
    max_positions: 10,
    stop_loss_pct: 0.05,
    take_profit_pct: 0.15,
    momentum_buy_threshold: 0.15,
    momentum_sell_threshold: -0.10,
    rebalance_frequency: 5,
  });

  const [symbolInput, setSymbolInput] = useState(config.symbols.join(", "));

  // Presets
  const presets: Preset[] = [
    {
      name: "Conservative",
      description: "Lower risk with smaller positions",
      config: {
        position_size_pct: 0.05,
        max_positions: 15,
        stop_loss_pct: 0.03,
        take_profit_pct: 0.10,
        momentum_buy_threshold: 0.20,
        momentum_sell_threshold: -0.15,
        rebalance_frequency: 7,
      },
    },
    {
      name: "Moderate",
      description: "Balanced risk/reward",
      config: {
        position_size_pct: 0.10,
        max_positions: 10,
        stop_loss_pct: 0.05,
        take_profit_pct: 0.15,
        momentum_buy_threshold: 0.15,
        momentum_sell_threshold: -0.10,
        rebalance_frequency: 5,
      },
    },
    {
      name: "Aggressive",
      description: "Higher risk for higher returns",
      config: {
        position_size_pct: 0.15,
        max_positions: 7,
        stop_loss_pct: 0.08,
        take_profit_pct: 0.25,
        momentum_buy_threshold: 0.10,
        momentum_sell_threshold: -0.08,
        rebalance_frequency: 3,
      },
    },
  ];

  const applyPreset = (preset: Preset) => {
    setConfig(prev => ({ ...prev, ...preset.config }));
  };

  const runBacktest = async () => {
    setIsLoading(true);
    setError(null);
    setResults(null);

    // Parse symbols from input
    const symbols = symbolInput
      .split(",")
      .map(s => s.trim().toUpperCase())
      .filter(s => s.length > 0);

    const requestConfig = { ...config, symbols };

    try {
      const response = await fetch("http://localhost:8000/api/v1/dashboard/backtest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestConfig),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Backtest failed");
      }

      const data: BacktestResponse = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">
            Momentum Strategy Backtester
          </h2>
          <p className="text-gray-400 mt-1">
            Test the AI momentum algorithm against historical data
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 px-2 py-1 bg-gray-800 rounded">
            Simulated Results
          </span>
        </div>
      </div>

      {/* Configuration Panel */}
      <div className="bg-gray-800/50 rounded-2xl border border-gray-700 p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Main Settings */}
          <div className="space-y-4">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Test Configuration
            </h3>

            {/* Symbols */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Symbols (comma-separated)
              </label>
              <input
                type="text"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="AAPL, MSFT, GOOGL..."
              />
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={config.start_date}
                  onChange={(e) => setConfig(prev => ({ ...prev, start_date: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={config.end_date}
                  onChange={(e) => setConfig(prev => ({ ...prev, end_date: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Initial Capital */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Initial Capital: {formatCurrency(config.initial_capital)}
              </label>
              <input
                type="range"
                min="10000"
                max="1000000"
                step="10000"
                value={config.initial_capital}
                onChange={(e) => setConfig(prev => ({ ...prev, initial_capital: parseInt(e.target.value) }))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>$10K</span>
                <span>$1M</span>
              </div>
            </div>
          </div>

          {/* Right Column - Presets & Advanced */}
          <div className="space-y-4">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Strategy Presets
            </h3>

            <div className="grid grid-cols-3 gap-2">
              {presets.map((preset) => (
                <button
                  key={preset.name}
                  onClick={() => applyPreset(preset)}
                  className="p-3 border border-gray-700 rounded-lg hover:bg-gray-700 transition-colors text-left"
                >
                  <div className="font-medium text-sm text-white">
                    {preset.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{preset.description}</div>
                </button>
              ))}
            </div>

            {/* Advanced Settings Toggle */}
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-blue-400 hover:underline flex items-center gap-1"
            >
              {showAdvanced ? "Hide" : "Show"} Advanced Settings
              <svg 
                className={`w-4 h-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`} 
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showAdvanced && (
              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Position Size: {(config.position_size_pct * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0.01"
                    max="0.25"
                    step="0.01"
                    value={config.position_size_pct}
                    onChange={(e) => setConfig(prev => ({ ...prev, position_size_pct: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Max Positions: {config.max_positions}
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="1"
                    value={config.max_positions}
                    onChange={(e) => setConfig(prev => ({ ...prev, max_positions: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Stop Loss: {(config.stop_loss_pct * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0.01"
                    max="0.15"
                    step="0.01"
                    value={config.stop_loss_pct}
                    onChange={(e) => setConfig(prev => ({ ...prev, stop_loss_pct: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Take Profit: {(config.take_profit_pct * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0.05"
                    max="0.40"
                    step="0.01"
                    value={config.take_profit_pct}
                    onChange={(e) => setConfig(prev => ({ ...prev, take_profit_pct: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Buy Threshold: {(config.momentum_buy_threshold * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0.05"
                    max="0.35"
                    step="0.01"
                    value={config.momentum_buy_threshold}
                    onChange={(e) => setConfig(prev => ({ ...prev, momentum_buy_threshold: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Rebalance: Every {config.rebalance_frequency} days
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="1"
                    value={config.rebalance_frequency}
                    onChange={(e) => setConfig(prev => ({ ...prev, rebalance_frequency: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Run Button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={runBacktest}
            disabled={isLoading}
            className={`
              px-6 py-3 rounded-xl font-semibold text-white
              flex items-center gap-2
              ${isLoading 
                ? "bg-gray-400 cursor-not-allowed" 
                : "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
              }
              transition-all shadow-lg hover:shadow-xl
            `}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Running Simulation...
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Run Backtest
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 flex items-center gap-3">
          <svg className="w-5 h-5 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-red-300">{error}</span>
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div className="space-y-6">
          {/* Performance Overview */}
          <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl p-6 text-white">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Performance Summary
            </h3>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-gray-400 text-sm">Total Return</div>
                <div className={`text-3xl font-bold ${results.total_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {formatPercent(results.total_return)}
                </div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Annualized</div>
                <div className={`text-3xl font-bold ${results.annualized_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {formatPercent(results.annualized_return)}
                </div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Sharpe Ratio</div>
                <div className="text-3xl font-bold">{results.sharpe_ratio.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Max Drawdown</div>
                <div className="text-3xl font-bold text-orange-400">-{results.max_drawdown.toFixed(1)}%</div>
              </div>
            </div>

            {/* Equity Curve */}
            <div className="mt-6">
              <div className="text-gray-400 text-sm mb-2">Equity Curve</div>
              <EquityCurveChart data={results.equity_curve} dates={results.dates} />
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Win Rate"
              value={`${results.win_rate.toFixed(1)}%`}
              subValue={`${results.winning_trades}W / ${results.losing_trades}L`}
              isPositive={results.win_rate >= 50}
            />
            <MetricCard
              label="Profit Factor"
              value={results.profit_factor.toFixed(2)}
              subValue="Gross profit / Gross loss"
              isPositive={results.profit_factor >= 1}
            />
            <MetricCard
              label="Avg Trade"
              value={formatPercent(results.avg_trade_return)}
              subValue={`${results.avg_holding_days.toFixed(0)} days avg hold`}
              isPositive={results.avg_trade_return >= 0}
            />
            <MetricCard
              label="Alpha vs SPY"
              value={formatPercent(results.alpha)}
              subValue={`Benchmark: ${formatPercent(results.benchmark_return)}`}
              isPositive={results.alpha >= 0}
            />
          </div>

          {/* Stats Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
              <h4 className="font-medium text-white mb-3">Trade Statistics</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Total Trades</span>
                  <span className="font-medium">{results.total_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Winning Trades</span>
                  <span className="font-medium text-green-400">{results.winning_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Losing Trades</span>
                  <span className="font-medium text-red-400">{results.losing_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Sortino Ratio</span>
                  <span className="font-medium">{results.sortino_ratio.toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
              <h4 className="font-medium text-white mb-3">Time Period</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Start Date</span>
                  <span className="font-medium">{new Date(results.start_date).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">End Date</span>
                  <span className="font-medium">{new Date(results.end_date).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Trading Days</span>
                  <span className="font-medium">{results.trading_days}</span>
                </div>
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
              <h4 className="font-medium text-white mb-3">Final Value</h4>
              <div className="text-3xl font-bold text-white">
                {formatCurrency(results.equity_curve[results.equity_curve.length - 1] || config.initial_capital)}
              </div>
              <div className={`text-sm mt-1 ${results.total_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                {results.total_return >= 0 ? "+" : ""}{formatCurrency(results.equity_curve[results.equity_curve.length - 1] - config.initial_capital)}
              </div>
            </div>
          </div>

          {/* Trade History */}
          <div className="bg-gray-800/50 rounded-2xl border border-gray-700 overflow-hidden">
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Trade History ({results.trades.length} trades)
              </h3>
            </div>
            <div className="max-h-96 overflow-y-auto">
              <TradeList trades={results.trades} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
