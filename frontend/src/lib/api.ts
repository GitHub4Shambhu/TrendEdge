/**
 * TrendEdge Frontend - API Client
 *
 * Centralized API client for backend communication.
 * All API calls go through this module for consistency.
 */

// Use environment variable for API URL, with fallback for local development
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export interface MomentumScore {
  symbol: string;
  asset_type: "stock" | "etf" | "option" | "future";
  score: number;
  signal: "buy" | "sell" | "hold";
  confidence: number;
  price: number;
  price_change_pct: number;
  volume_ratio: number;
  sentiment_score: number | null;
  updated_at: string;
}

export interface TopOpportunity {
  rank: number;
  momentum: MomentumScore;
  reason: string;
  risk_level: "low" | "medium" | "high";
  target_price: number | null;
  stop_loss: number | null;
}

export interface DashboardData {
  top_stocks: TopOpportunity[];
  top_etfs: TopOpportunity[];
  top_options: TopOpportunity[];
  market_sentiment: number;
  last_updated: string;
}

// ── Max Risk Momentum Types ─────────────────────────────────────

export interface MaxRiskScoreResult {
  symbol: string;
  rank: number;
  price: number;
  r1w: number;
  r1m: number;
  return_3m: number;
  return_6m: number;
  return_12m: number;
  rs3m: number;
  rs6m: number;
  rs12m: number;
  vexp: number;
  breakout_factor: number;
  is_20d_high: boolean;
  vol_accel: number;
  sma_50: number;
  sma_200: number;
  price_to_200dma: number;
  max_risk_score: number;
  turbo_score: number;
  below_50dma: boolean;
  stop_price: number;
  signal: string;
  timestamp: string;
}

export interface MaxRiskRegimeResult {
  risk_on: boolean;
  qqq_close: number;
  qqq_200sma: number;
  qqq_distance_pct: number;
  spy_close: number;
  spy_200sma: number;
  description: string;
}

export interface MaxRiskPortfolioResponse {
  top_picks: MaxRiskScoreResult[];
  full_ranking: MaxRiskScoreResult[];
  regime: MaxRiskRegimeResult;
  use_turbo: boolean;
  scanned_at: string;
  total_scanned: number;
}

// ── Institutional Momentum Types ────────────────────────────────

export interface MarketRegimeResult {
  regime: "BULL" | "BEAR" | "NEUTRAL";
  spy_above_200dma: boolean;
  spy_distance_200dma: number;
  market_volatility: number;
  breadth: number;
  description: string;
}

export interface InstitutionalMomentumResult {
  symbol: string;
  rank: number;
  quintile: number;
  price: number;
  r12_skip1: number;
  r6_skip1: number;
  r3_skip1: number;
  r1: number;
  volatility: number;
  risk_adj_return: number;
  vol_scaled_weight: number;
  raw_score: number;
  vol_adjusted_score: number;
  avg_dollar_volume: number;
  passes_liquidity: boolean;
  above_200dma: boolean;
  distance_to_200dma: number;
  signal: string;
  timestamp: string;
}

export interface InstitutionalPortfolioResponse {
  portfolio: InstitutionalMomentumResult[];
  full_ranking: InstitutionalMomentumResult[];
  market_regime: MarketRegimeResult;
  breadth: number;
  vol_scaling_enabled: boolean;
  total_scanned: number;
}

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get main dashboard data with top opportunities
   */
  async getDashboard(): Promise<DashboardData> {
    return this.fetch<DashboardData>("/dashboard/");
  }

  /**
   * Get momentum scores for specific symbols
   */
  async getStockMomentum(symbols: string[]): Promise<MomentumScore[]> {
    const symbolsParam = symbols.join(",");
    return this.fetch<MomentumScore[]>(`/dashboard/stocks?symbols=${symbolsParam}`);
  }

  /**
   * Get detailed momentum for a single symbol
   */
  async getSymbolMomentum(
    symbol: string,
    assetType: string = "stock"
  ): Promise<MomentumScore> {
    return this.fetch<MomentumScore>(
      `/dashboard/symbol/${symbol}?asset_type=${assetType}`
    );
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseUrl.replace("/api/v1", "")}/health`);
    return response.json();
  }

  // ── Max Risk Momentum Methods ───────────────────────────────

  /**
   * Get Max Risk portfolio (top picks + full ranking)
   */
  async getMaxRiskPortfolio(
    topN: number = 5,
    useTurbo: boolean = false
  ): Promise<MaxRiskPortfolioResponse> {
    return this.fetch<MaxRiskPortfolioResponse>(
      `/dashboard/max-risk-portfolio?top_n=${topN}&use_turbo=${useTurbo}`
    );
  }

  /**
   * Get Max Risk scan (ranked list)
   */
  async getMaxRiskScan(
    limit: number = 20,
    useTurbo: boolean = false
  ): Promise<MaxRiskScoreResult[]> {
    return this.fetch<MaxRiskScoreResult[]>(
      `/dashboard/max-risk-scan?limit=${limit}&use_turbo=${useTurbo}`
    );
  }

  /**
   * Get Max Risk analysis for a single symbol
   */
  async getMaxRiskAnalysis(symbol: string): Promise<MaxRiskScoreResult> {
    return this.fetch<MaxRiskScoreResult>(
      `/dashboard/max-risk-analyze/${symbol}`
    );
  }

  // ── Institutional Momentum Methods ──────────────────────────

  /**
   * Get institutional momentum portfolio (holdings + ranking + regime)
   */
  async getInstitutionalPortfolio(
    topN: number = 10,
    volScaling: boolean = true
  ): Promise<InstitutionalPortfolioResponse> {
    return this.fetch<InstitutionalPortfolioResponse>(
      `/dashboard/institutional-portfolio?top_n=${topN}&vol_scaling=${volScaling}`
    );
  }

  /**
   * Get institutional momentum scan (ranked list)
   */
  async getInstitutionalScan(
    limit: number = 20,
    volAdjusted: boolean = true
  ): Promise<InstitutionalMomentumResult[]> {
    return this.fetch<InstitutionalMomentumResult[]>(
      `/dashboard/institutional-scan?limit=${limit}&vol_adjusted=${volAdjusted}`
    );
  }

  /**
   * Get institutional momentum analysis for a single symbol
   */
  async getInstitutionalAnalysis(
    symbol: string
  ): Promise<InstitutionalMomentumResult> {
    return this.fetch<InstitutionalMomentumResult>(
      `/dashboard/institutional-analyze/${symbol}`
    );
  }
}

// Export singleton instance
export const apiClient = new APIClient();

export default apiClient;
