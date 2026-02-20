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


class DashboardResponse(BaseModel):
    """Main dashboard API response."""
    top_stocks: List[TopOpportunity] = Field(default_factory=list)
    top_etfs: List[TopOpportunity] = Field(default_factory=list)
    top_options: List[TopOpportunity] = Field(default_factory=list)
    market_sentiment: float = Field(..., description="Overall market sentiment")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


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
    trades: List[TradeResult]
    daily_snapshots: List[DailySnapshotResult]
    
    # Equity curve for charting
    equity_curve: List[float] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)
