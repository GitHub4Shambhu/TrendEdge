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
}

// Export singleton instance
export const apiClient = new APIClient();

export default apiClient;
