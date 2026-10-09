/**
 * TrendEdge Frontend - Demo Data
 *
 * Fallback data for the lookup, watchlist and sector rotation features when
 * the backend is unreachable (e.g. the static GitHub Pages build).
 * Per-symbol values are derived from a hash of the ticker so they stay stable.
 */

import type {
  Consensus,
  EngineSignal,
  SectorRotationResponse,
  SymbolLookupResponse,
  WatchlistItem,
  WatchlistResponse,
} from "./api";

// Reference prices so well-known tickers look plausible in demo mode
const DEMO_PRICES: Record<string, number> = {
  NVDA: 229.84, AAPL: 337.33, MSFT: 535.75, TSLA: 355.0, PLTR: 142.5,
  SPY: 668.2, QQQ: 598.4, META: 700.25, AMZN: 231.6, GOOGL: 245.1,
};

/** Deterministic PRNG (mulberry32) seeded from the ticker. */
function rngFor(symbol: string): () => number {
  let seed = 0;
  for (const ch of symbol) seed = (Math.imul(seed, 31) + ch.charCodeAt(0)) | 0;
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const r2 = (n: number) => Math.round(n * 100) / 100;

function consensusOf(signals: EngineSignal[]): [Consensus, number, number] {
  const buys = signals.filter((s) => s === "BUY").length;
  const sells = signals.filter((s) => s === "SELL").length;
  if (buys >= 2) return ["BULLISH", buys, sells];
  if (sells >= 2) return ["BEARISH", buys, sells];
  if (buys || sells) return ["MIXED", buys, sells];
  return ["NEUTRAL", buys, sells];
}

export function mockLookup(rawSymbol: string): SymbolLookupResponse {
  const symbol = rawSymbol.trim().toUpperCase();
  const rand = rngFor(symbol);
  const between = (lo: number, hi: number) => lo + rand() * (hi - lo);
  const now = new Date().toISOString();

  const price = DEMO_PRICES[symbol] ?? r2(between(20, 400));
  const change = r2(between(-3, 3.5));
  const trend = between(-1, 1); // shared drift so the engines roughly agree

  const composite = r2((trend * 0.25 + between(-0.05, 0.05)) * 100) / 100;
  const advSignal: EngineSignal = composite > 0.05 ? "BUY" : composite < -0.05 ? "SELL" : "HOLD";

  const r1w = r2(trend * 3 + between(-2, 2));
  const r1m = r2(trend * 8 + between(-3, 3));
  const r3m = r2(trend * 18 + between(-5, 5));
  const r6m = r2(trend * 30 + between(-8, 8));
  const r12m = r2(trend * 50 + between(-10, 10));
  const maxRisk = r2(trend * 25 + between(-4, 4));
  const below50 = trend < -0.3;
  const mrSignal: EngineSignal = maxRisk > 15 && !below50 ? "BUY" : below50 || maxRisk < -10 ? "SELL" : "HOLD";

  const vol = r2(between(18, 65));
  const instRaw = r2(trend * 35 + between(-5, 5));
  const dist200 = r2(trend * 20 + between(-4, 4));
  const instSignal: EngineSignal = instRaw > 15 && dist200 > 0 ? "BUY" : instRaw < -10 || dist200 <= 0 ? "SELL" : "HOLD";

  const [consensus, buy_votes, sell_votes] = consensusOf([advSignal, mrSignal, instSignal]);

  return {
    symbol,
    price,
    price_change_pct: change,
    consensus,
    buy_votes,
    sell_votes,
    timestamp: now,
    advanced: {
      symbol,
      signal: advSignal,
      composite_score: composite,
      price,
      price_change: change,
      momentum: {
        roc_5d: r1w,
        roc_10d: r2((r1w + r1m) / 2),
        roc_20d: r1m,
        roc_60d: r3m,
        trend_score: r2(trend),
      },
      volume: { ratio: r2(between(0.6, 2.2)), trend: r2(between(-0.3, 0.4)), accumulation: r2(trend * 0.5) },
      technicals: {
        rsi_14: r2(50 + trend * 18 + between(-6, 6)),
        rsi_7: r2(50 + trend * 22 + between(-8, 8)),
        macd_signal: r2(trend * 1.5),
        macd_histogram: r2(trend * 0.8 + between(-0.2, 0.2)),
        bb_position: r2(0.5 + trend * 0.35),
        adx: r2(between(15, 40)),
        atr_percent: r2(between(1, 4.5)),
        sma_20_distance: r2(trend * 4),
        sma_50_distance: r2(trend * 8),
        sma_200_distance: dist200,
        ema_crossover: r2(trend * 2),
        obv_trend: r2(trend * 0.6),
        mfi: r2(50 + trend * 20),
        stochastic_k: r2(50 + trend * 30),
        stochastic_d: r2(50 + trend * 26),
      },
      ai_prediction: { score: r2(trend * 0.6), confidence: r2(between(0.55, 0.85)) },
      risk: { volatility_score: r2(vol / 100) },
      timestamp: now,
    },
    max_risk: {
      symbol,
      rank: 1,
      price,
      r1w,
      r1m,
      return_3m: r3m,
      return_6m: r6m,
      return_12m: r12m,
      rs3m: r2(r3m - 3.9),
      rs6m: r2(r6m - 14.1),
      rs12m: r2(r12m - 17.3),
      vexp: r2(between(-0.5, 0.5)),
      breakout_factor: trend > 0.5 ? 1 : 0,
      is_20d_high: trend > 0.5,
      vol_accel: r2(between(-0.4, 0.4)),
      sma_50: r2(price / (1 + trend * 0.08)),
      sma_200: r2(price / (1 + dist200 / 100)),
      price_to_200dma: r2(1 + dist200 / 100),
      max_risk_score: maxRisk,
      turbo_score: r2(maxRisk + 0.05 * (r1m - r3m)),
      below_50dma: below50,
      stop_price: r2(price * 0.85),
      signal: mrSignal,
      timestamp: now,
    },
    institutional: {
      symbol,
      rank: 1,
      quintile: 3,
      price,
      r12_skip1: r2(r12m - r1m),
      r6_skip1: r2(r6m - r1m),
      r3_skip1: r2(r3m - r1m),
      r1: r1m,
      volatility: vol,
      risk_adj_return: r2((r12m - r1m) / vol),
      vol_scaled_weight: r2(1 / vol),
      raw_score: instRaw,
      vol_adjusted_score: r2(instRaw * (30 / vol)),
      avg_dollar_volume: Math.round(between(2e7, 5e9)),
      passes_liquidity: price > 30,
      above_200dma: dist200 > 0,
      distance_to_200dma: dist200,
      signal: instSignal,
      timestamp: now,
    },
  };
}

export function mockWatchlist(symbols: string[]): WatchlistResponse {
  const items: WatchlistItem[] = symbols.map((s) => {
    const r = mockLookup(s);
    return {
      symbol: r.symbol,
      price: r.price,
      price_change_pct: r.price_change_pct,
      advanced_signal: r.advanced!.signal,
      advanced_score: r.advanced!.composite_score,
      max_risk_signal: r.max_risk!.signal as EngineSignal,
      max_risk_score: r.max_risk!.max_risk_score,
      institutional_signal: r.institutional!.signal as EngineSignal,
      institutional_score: r.institutional!.vol_adjusted_score,
      consensus: r.consensus,
      data_source: "live",
    };
  });
  return { items, not_found: [], scanned_at: new Date().toISOString() };
}

// Returns/RS/score from a real /sector-rotation response (Oct 2026); prices illustrative
type SectorRow = [string, string, number, number, number, number, number, number, number, number, number, EngineSignal];
const SECTOR_ROWS: SectorRow[] = [
  // symbol, name, price, 1W, 1M, 3M, 6M, 12M, RS3M, vs200D, score, signal
  ["XLE", "Energy", 98.4, 2.64, 0.57, 15.03, 15.5, 52.65, 11.15, 15.5, 12.4, "HOLD"],
  ["XLK", "Technology", 301.2, -0.96, 6.16, 8.5, 37.0, 37.85, 4.62, 19.9, 11.3, "HOLD"],
  ["XLV", "Health Care", 152.7, 2.06, 3.69, 8.33, 16.4, 20.44, 4.44, 9.6, 7.1, "HOLD"],
  ["XLP", "Consumer Staples", 81.9, 2.99, 0.76, 0.71, 3.7, 9.88, -3.18, 0.8, 1.4, "SELL"],
  ["XLF", "Financials", 52.3, 1.7, -3.95, -2.12, 6.8, 4.39, -6.01, 2.8, -0.9, "SELL"],
  ["XLRE", "Real Estate", 41.6, 2.27, -3.4, -5.7, -1.6, 4.7, -9.59, -2.3, -1.5, "SELL"],
  ["XLI", "Industrials", 148.9, -0.41, -1.46, -5.87, -1.4, 11.77, -9.76, -1.4, -2.4, "SELL"],
  ["XLB", "Materials", 88.1, 0.05, -2.35, -1.75, -4.3, 13.72, -5.64, -1.7, -3.3, "SELL"],
  ["XLY", "Consumer Discretionary", 224.5, 2.32, 0.24, -2.3, -0.4, -3.15, -6.19, -2.3, -5.2, "SELL"],
  ["XLU", "Utilities", 79.8, 3.52, -1.68, -8.78, -9.6, -6.03, -12.66, -5.5, -5.5, "SELL"],
  ["XLC", "Communication Services", 108.3, -0.99, -1.54, -0.52, -3.2, -2.65, -4.41, -2.2, -5.8, "SELL"],
];

export const MOCK_SECTOR_ROTATION: SectorRotationResponse = {
  sectors: SECTOR_ROWS.map(([symbol, name, price, r1w, r1m, r3m, r6m, r12m, rs3m, dist, score, signal], i) => ({
    symbol, name, rank: i + 1, price, r1w, r1m, r3m, r6m, r12m, rs3m,
    rs6m: r2(r6m - 14.1), distance_to_200dma: dist, momentum_score: score, signal,
  })),
  benchmark: {
    symbol: "SPY", name: "S&P 500", rank: 0, price: 668.2, r1w: 0.55, r1m: 2.19, r3m: 3.89,
    r6m: 14.1, r12m: 17.34, rs3m: 0, rs6m: 0, distance_to_200dma: 8.3, momentum_score: 2.8, signal: "HOLD",
  },
  leaders: ["XLE", "XLK", "XLV"],
  laggards: ["XLC", "XLU", "XLY"],
  scanned_at: new Date().toISOString(),
};
