"""
TrendEdge Backend - Pydantic Schemas

Defines all request/response models for the API.
Clear typing enables AI agents to understand data structures.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    """Supported asset types for momentum analysis."""
    STOCK = "stock"
    ETF = "etf"
    OPTION = "option"
    FUTURE = "future"


class SignalType(str, Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class MomentumScore(BaseModel):
    """Momentum score for a single asset."""
    symbol: str = Field(..., description="Ticker symbol")
    asset_type: AssetType = Field(..., description="Type of asset")
    score: float = Field(..., ge=-1.0, le=1.0, description="Momentum score (-1 to 1)")
    signal: SignalType = Field(..., description="Trading signal")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level")
    price: float = Field(..., description="Current price")
    price_change_pct: float = Field(..., description="Price change percentage")
    volume_ratio: float = Field(..., description="Volume vs average ratio")
    sentiment_score: Optional[float] = Field(None, description="Social sentiment score")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TopOpportunity(BaseModel):
    """Top trading opportunity with full analysis."""
    rank: int = Field(..., ge=1, description="Opportunity rank")
    momentum: MomentumScore = Field(..., description="Momentum details")
    reason: str = Field(..., description="AI-generated explanation")
    risk_level: str = Field(..., description="Risk assessment: low/medium/high")
    target_price: Optional[float] = Field(None, description="Predicted target price")
    stop_loss: Optional[float] = Field(None, description="Suggested stop loss")
    market_cap: Optional[float] = Field(None, description="Market capitalization in dollars")


class DashboardResponse(BaseModel):
    """Main dashboard API response."""
    top_stocks: List[TopOpportunity] = Field(default_factory=list)
    top_etfs: List[TopOpportunity] = Field(default_factory=list)
    top_options: List[TopOpportunity] = Field(default_factory=list)
    market_sentiment: float = Field(..., description="Overall market sentiment")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = Field("live", description="'live' if all data from yfinance, 'stale' if any mock fallback used")


class SymbolSearchRequest(BaseModel):
    """Request to search for a specific symbol."""
    symbol: str = Field(..., min_length=1, max_length=10)
    asset_type: Optional[AssetType] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Backtesting Schemas
# ============================================================================

class BacktestRequest(BaseModel):
    """Request to run a backtest."""
    symbols: List[str] = Field(
        default=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AMD", "TSLA"],
        description="List of symbols to backtest"
    )
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(default=100000.0, ge=1000, description="Starting capital")
    position_size_pct: float = Field(default=0.1, ge=0.01, le=0.5, description="Position size as % of portfolio")
    max_positions: int = Field(default=10, ge=1, le=50, description="Maximum concurrent positions")
    stop_loss_pct: float = Field(default=0.05, ge=0.01, le=0.20, description="Stop loss percentage")
    take_profit_pct: float = Field(default=0.15, ge=0.05, le=0.50, description="Take profit percentage")
    momentum_buy_threshold: float = Field(default=0.15, ge=0.05, le=0.5, description="Momentum score to trigger BUY")
    momentum_sell_threshold: float = Field(default=-0.10, ge=-0.5, le=-0.01, description="Momentum score to trigger SELL")
    rebalance_frequency: int = Field(default=5, ge=1, le=30, description="Days between rebalancing")


class TradeResult(BaseModel):
    """Single trade result."""
    symbol: str
    action: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime]
    exit_price: Optional[float]
    shares: float
    pnl: float
    pnl_percent: float
    holding_days: int
    exit_reason: str


class DailySnapshotResult(BaseModel):
    """Daily portfolio snapshot."""
    date: datetime
    portfolio_value: float
    cash: float
    positions_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    num_positions: int


class BacktestResponse(BaseModel):
    """Full backtest results response."""
    # Performance metrics
    total_return: float = Field(..., description="Total return percentage")
    annualized_return: float = Field(..., description="Annualized return")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown")
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_return: float
    avg_holding_days: float
    
    # Benchmark comparison
    benchmark_return: float
    alpha: float
    
    # Time info
    start_date: datetime
    end_date: datetime
    trading_days: int

    # Detailed data
    trades: List[TradeResult] = Field(default_factory=list)
    daily_snapshots: List[DailySnapshotResult] = Field(default_factory=list)

    # Equity curve for charting
    equity_curve: List[float] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)


# ============================================================================
# Max Risk Momentum Schemas
# ============================================================================

class MaxRiskScoreResult(BaseModel):
    """Max Risk Momentum Score for a single symbol."""
    symbol: str = Field(..., description="Ticker symbol")
    rank: int = Field(..., ge=1, description="Rank by score")
    price: float = Field(..., description="Current price")

    # Absolute returns (close-to-close)
    r1w: float = Field(0.0, description="1-week (5d) return %")
    r1m: float = Field(0.0, description="1-month (21d) return %")
    return_3m: float = Field(..., description="3-month (63d) return %")
    return_6m: float = Field(..., description="6-month (126d) return %")
    return_12m: float = Field(..., description="12-month (252d) return %")

    # Relative strength vs SPY
    rs3m: float = Field(0.0, description="R3M - SPY_R3M %")
    rs6m: float = Field(0.0, description="R6M - SPY_R6M %")
    rs12m: float = Field(0.0, description="R12M - SPY_R12M %")

    # Volatility expansion
    vexp: float = Field(0.0, description="ln(stdev10d/stdev60d), clipped [-1,+1]")

    # Factors
    breakout_factor: float = Field(..., description="1 if Close >= 20D High, else 0")
    is_20d_high: bool = Field(False, description="At 20-day high?")
    vol_accel: float = Field(..., description="ln(AvgVol5/AvgVol50), clipped [-1,+1]")

    # Moving averages
    sma_50: float = Field(..., description="50-day SMA")
    sma_200: float = Field(..., description="200-day SMA")
    price_to_200dma: float = Field(..., description="Price / 200DMA ratio")

    # Scores
    max_risk_score: float = Field(..., description="11-factor MaxRiskMomentum score")
    turbo_score: float = Field(..., description="MaxRisk + 0.05*(R1M-R3M)")

    # Exit conditions
    below_50dma: bool = Field(False, description="Close below 50DMA")
    stop_price: float = Field(..., description="-15% hard stop price")

    signal: str = Field(..., description="BUY / SELL / HOLD")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MaxRiskRegimeResult(BaseModel):
    """QQQ-based regime filter result."""
    risk_on: bool = Field(True, description="QQQ_Close > QQQ_200SMA")
    qqq_close: float = Field(0.0)
    qqq_200sma: float = Field(0.0)
    qqq_distance_pct: float = Field(0.0, description="QQQ % above/below 200SMA")
    spy_close: float = Field(0.0)
    spy_200sma: float = Field(0.0)
    description: str = Field("")


class MaxRiskPortfolioResponse(BaseModel):
    """Max Risk portfolio with top picks and full scan."""
    top_picks: List[MaxRiskScoreResult] = Field(default_factory=list, description="Top picks to buy")
    full_ranking: List[MaxRiskScoreResult] = Field(default_factory=list, description="Full ranked list")
    regime: MaxRiskRegimeResult = Field(default_factory=MaxRiskRegimeResult)
    use_turbo: bool = Field(False, description="Whether TurboScore was used for ranking")
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    total_scanned: int = Field(0, description="Total symbols scanned")
    data_source: str = Field("live", description="'live' if all data from yfinance, 'stale' if any mock fallback used")


# ============================================================================
# Institutional Momentum Schemas
# ============================================================================

class MarketRegimeResult(BaseModel):
    """Market regime assessment."""
    regime: str = Field(..., description="BULL / BEAR / NEUTRAL")
    spy_above_200dma: bool = Field(True)
    spy_distance_200dma: float = Field(0.0, description="SPY % distance to 200DMA")
    market_volatility: float = Field(0.0, description="Realized market vol %")
    breadth: float = Field(0.0, description="% of universe above 200DMA")
    description: str = Field("")


class InstitutionalMomentumResult(BaseModel):
    """Institutional momentum score for a single symbol."""
    symbol: str = Field(..., description="Ticker symbol")
    rank: int = Field(..., ge=1)
    quintile: int = Field(3, ge=1, le=5, description="1=top 20%, 5=bottom 20%")
    price: float = Field(...)

    # Skip-month returns
    r12_skip1: float = Field(..., description="12M return skipping last month %")
    r6_skip1: float = Field(..., description="6M return skipping last month %")
    r3_skip1: float = Field(..., description="3M return skipping last month %")
    r1: float = Field(..., description="Last 1-month return (skipped) %")

    # Volatility
    volatility: float = Field(..., description="Annualized vol %")
    risk_adj_return: float = Field(..., description="Return / Vol ratio")
    vol_scaled_weight: float = Field(..., description="Inverse-vol portfolio weight")

    # Scores
    raw_score: float = Field(..., description="Raw institutional momentum score")
    vol_adjusted_score: float = Field(..., description="Volatility-adjusted score")

    # Filters
    avg_dollar_volume: float = Field(0.0)
    passes_liquidity: bool = Field(False)
    above_200dma: bool = Field(False)
    distance_to_200dma: float = Field(0.0, description="% above/below 200DMA")

    signal: str = Field(..., description="BUY / SELL / HOLD")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class InstitutionalPortfolioResponse(BaseModel):
    """Institutional momentum portfolio response."""
    portfolio: List[InstitutionalMomentumResult] = Field(default_factory=list)
    full_ranking: List[InstitutionalMomentumResult] = Field(default_factory=list)
    market_regime: MarketRegimeResult = Field(...)
    breadth: float = Field(0.0, description="% of universe above 200DMA")
    vol_scaling_enabled: bool = Field(True)
    total_scanned: int = Field(0)
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = Field("live", description="'live' if all data from yfinance, 'stale' if any mock fallback used")


# ============================================================================
# Market Sentiment Schemas
# ============================================================================

# ============================================================================
# Market Cap Momentum Schemas
# ============================================================================

class MarketCapCategory(BaseModel):
    """Single market cap tier with its top opportunities."""
    tier: str = Field(..., description="Tier key: mega/large/medium/small/micro")
    label: str = Field(..., description="Human-readable tier label")
    opportunities: List[TopOpportunity] = Field(default_factory=list)
    total_scanned: int = Field(0, description="Symbols scanned in this tier")


class MarketCapMomentumResponse(BaseModel):
    """Response containing momentum opportunities grouped by market cap tier."""
    categories: List[MarketCapCategory] = Field(default_factory=list)
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = Field("live", description="'live' if all data from yfinance, 'stale' if any mock fallback used")


# ============================================================================
# Market Sentiment Schemas
# ============================================================================

class SentimentMetricDetail(BaseModel):
    """Single metric with Z-score and weight."""
    name: str = Field(..., description="Metric key")
    raw_value: float = Field(..., description="Current raw metric value")
    z_score: float = Field(..., description="Z-score within W window")
    weight: float = Field(..., description="Aggregation weight")
    weighted_z: float = Field(..., description="weight × z_score")
    description: str = Field("", description="Human-readable label")
    series: List[float] = Field(default_factory=list, description="Full W-day Z-score series")


class MarketSentimentResponse(BaseModel):
    """Complete market sentiment model output."""
    final_score: float = Field(..., ge=0.0, le=1.0, description="0-1 sentiment probability")
    regime: str = Field(..., description="Fear / Defensive / Neutral / Risk-On / Euphoria")
    trend_direction: str = Field(..., description="Rising / Falling / Flat")
    trend_slope: float = Field(..., description="Per-day slope of composite within W")
    composite_raw: float = Field(..., description="Raw weighted-Z sum before logistic")
    metrics: List[SentimentMetricDetail] = Field(default_factory=list)
    window_size: int = Field(20, description="Rolling window W (trading days)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = Field("live", description="'live' if computed from yfinance, 'stale' if fallback used")
