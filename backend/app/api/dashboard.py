"""
TrendEdge Backend - Dashboard API Routes

Provides endpoints for the main dashboard functionality.
All endpoints return typed responses for client type safety.
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

import asyncio

from app.schemas.momentum import (
    AssetType,
    DashboardResponse,
    MomentumScore,
    SignalType,
    TopOpportunity,
    BacktestRequest,
    BacktestResponse,
    TradeResult,
    DailySnapshotResult,
    MaxRiskScoreResult,
    MaxRiskPortfolioResponse,
    MaxRiskRegimeResult,
    InstitutionalMomentumResult,
    InstitutionalPortfolioResponse,
    MarketRegimeResult,
    SentimentMetricDetail,
    MarketSentimentResponse,
    MarketCapCategory,
    MarketCapMomentumResponse,
)
from app.services.momentum_service import get_momentum_service
from app.services.sentiment_service import get_sentiment_service
from app.services.advanced_momentum import get_momentum_algorithm, MomentumFactors
from app.services.stock_universe import get_quick_scan_universe, get_sector_etfs
from app.services.backtesting import get_backtesting_engine, BacktestConfig
from app.services.max_risk_momentum import get_max_risk_engine, MaxRiskFactors, RegimeData
from app.services.institutional_momentum import get_institutional_engine, InstitutionalFactors, MarketRegimeData
from app.services.market_sentiment import get_sentiment_engine, SentimentResult, SentimentMetric
from app.services.market_cap_universe import get_market_cap_service, MarketCapTier, TIER_ORDER, TIER_LABELS

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _factors_to_momentum_score(factors: MomentumFactors) -> MomentumScore:
    """Convert MomentumFactors to MomentumScore schema."""
    signal_map = {"BUY": SignalType.BUY, "SELL": SignalType.SELL, "HOLD": SignalType.HOLD}
    
    return MomentumScore(
        symbol=factors.symbol,
        asset_type=AssetType.STOCK,
        score=round(factors.composite_score, 4),
        signal=signal_map.get(factors.signal, SignalType.HOLD),
        confidence=round(factors.ml_confidence, 4),
        price=round(factors.price, 2),
        price_change_pct=round(factors.price_change, 2),
        volume_ratio=round(factors.volume_ratio, 2),
        sentiment_score=None,  # Will be added when sentiment is integrated
        updated_at=factors.timestamp,
    )


def _create_opportunity_from_factors(rank: int, factors: MomentumFactors) -> TopOpportunity:
    """Create a TopOpportunity from MomentumFactors."""
    momentum = _factors_to_momentum_score(factors)
    
    # Generate detailed reason based on multiple factors
    reasons = []
    
    # Momentum strength
    if factors.composite_score > 0.4:
        reasons.append("Strong bullish momentum")
    elif factors.composite_score > 0.2:
        reasons.append("Bullish momentum")
    elif factors.composite_score < -0.4:
        reasons.append("Strong bearish momentum")
    elif factors.composite_score < -0.2:
        reasons.append("Bearish momentum")
    
    # Technical factors
    if factors.technicals.rsi_14 < 35:
        reasons.append("oversold RSI")
    elif factors.technicals.rsi_14 > 65:
        reasons.append("overbought RSI")
    
    if factors.technicals.macd_histogram > 0:
        reasons.append("MACD bullish")
    
    if factors.technicals.sma_20_distance > 2:
        reasons.append("above 20-day MA")
    elif factors.technicals.sma_20_distance < -2:
        reasons.append("below 20-day MA")
    
    # Volume
    if factors.volume_ratio > 2.0:
        reasons.append("very high volume")
    elif factors.volume_ratio > 1.5:
        reasons.append("high volume")
    
    # ML confidence
    if factors.ml_confidence > 0.7:
        reasons.append(f"high AI confidence ({factors.ml_confidence:.0%})")
    
    # ADX trend strength
    if factors.technicals.adx > 30:
        reasons.append("strong trend")
    
    reason = ", ".join(reasons) if reasons else "Neutral signals"
    
    # Risk assessment
    risk_factors = 0
    if factors.technicals.atr_percent > 4:
        risk_factors += 1  # High volatility
    if factors.technicals.rsi_14 > 70 or factors.technicals.rsi_14 < 30:
        risk_factors += 1  # Extreme RSI
    if factors.ml_confidence < 0.5:
        risk_factors += 1  # Low confidence
    if abs(factors.roc_5d) > 10:
        risk_factors += 1  # Large recent move
    
    if risk_factors <= 1 and factors.ml_confidence > 0.6:
        risk_level = "low"
    elif risk_factors <= 2:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    # Calculate price targets
    target_price = None
    stop_loss = None
    
    if factors.signal == "BUY":
        # Target: Based on ATR and momentum strength
        target_pct = 3 + (factors.composite_score * 5) + (factors.technicals.adx / 20)
        target_price = round(factors.price * (1 + target_pct / 100), 2)
        
        # Stop loss: Based on ATR
        stop_pct = max(2, factors.technicals.atr_percent * 1.5)
        stop_loss = round(factors.price * (1 - stop_pct / 100), 2)
    elif factors.signal == "SELL":
        target_pct = 3 + (abs(factors.composite_score) * 5)
        target_price = round(factors.price * (1 - target_pct / 100), 2)
        stop_loss = round(factors.price * (1 + factors.technicals.atr_percent * 1.5 / 100), 2)
    
    return TopOpportunity(
        rank=rank,
        momentum=momentum,
        reason=reason.capitalize(),
        risk_level=risk_level,
        target_price=target_price,
        stop_loss=stop_loss,
    )


# Legacy function for backward compatibility
def _create_opportunity(rank: int, momentum: MomentumScore) -> TopOpportunity:
    """Create a TopOpportunity from a MomentumScore."""
    # Generate reason based on metrics
    reasons = []
    if momentum.score > 0.3:
        reasons.append("Strong bullish momentum")
    elif momentum.score > 0.1:
        reasons.append("Moderate bullish momentum")
    elif momentum.score < -0.3:
        reasons.append("Strong bearish momentum")
    elif momentum.score < -0.1:
        reasons.append("Moderate bearish momentum")

    if momentum.volume_ratio > 1.5:
        reasons.append("high volume surge")
    if momentum.sentiment_score and momentum.sentiment_score > 0.3:
        reasons.append("positive social sentiment")

    reason = ", ".join(reasons) if reasons else "Neutral momentum"

    # Determine risk level
    if abs(momentum.score) > 0.5 and momentum.confidence > 0.7:
        risk_level = "low"
    elif abs(momentum.score) > 0.3:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Calculate targets (simplified)
    target_price = None
    stop_loss = None
    if momentum.signal.value == "buy":
        target_price = round(momentum.price * 1.05, 2)  # 5% target
        stop_loss = round(momentum.price * 0.97, 2)  # 3% stop
    elif momentum.signal.value == "sell":
        target_price = round(momentum.price * 0.95, 2)
        stop_loss = round(momentum.price * 1.03, 2)

    return TopOpportunity(
        rank=rank,
        momentum=momentum,
        reason=reason.capitalize(),
        risk_level=risk_level,
        target_price=target_price,
        stop_loss=stop_loss,
    )


@router.get("/", response_model=DashboardResponse)
async def get_dashboard(use_advanced: bool = Query(True, description="Use advanced AI algorithm")):
    """
    Get the main dashboard data with top opportunities.
    
    Returns top stocks, ETFs, and options ranked by momentum score.
    Uses advanced AI-based momentum algorithm for real market scanning.
    """
    sentiment_service = get_sentiment_service()
    
    if use_advanced:
        # Use advanced AI momentum algorithm
        algorithm = get_momentum_algorithm()
        
        # Scan stocks
        stock_symbols = get_quick_scan_universe()[:30]  # Top 30 for speed
        stock_factors = await algorithm.scan_universe(stock_symbols)
        
        # Filter for BUY signals and take top 5
        buy_stocks = [f for f in stock_factors if f.signal == "BUY"][:5]
        top_stocks = [
            _create_opportunity_from_factors(i + 1, factors)
            for i, factors in enumerate(buy_stocks)
        ]
        
        # Scan ETFs
        etf_symbols = get_sector_etfs()
        etf_factors = await algorithm.scan_universe(etf_symbols)
        buy_etfs = [f for f in etf_factors if f.signal == "BUY"][:5]
        top_etfs = [
            _create_opportunity_from_factors(i + 1, factors)
            for i, factors in enumerate(buy_etfs)
        ]
        
        # If no BUY signals, show top momentum (even HOLD)
        if not top_stocks and stock_factors:
            top_stocks = [
                _create_opportunity_from_factors(i + 1, factors)
                for i, factors in enumerate(stock_factors[:5])
            ]
        
        if not top_etfs and etf_factors:
            top_etfs = [
                _create_opportunity_from_factors(i + 1, factors)
                for i, factors in enumerate(etf_factors[:5])
            ]
    else:
        # Fallback to legacy service
        momentum_service = get_momentum_service()
        default_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "CRM"]
        default_etfs = ["SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK", "XLF", "XLE", "XLK"]
        
        stock_scores = await momentum_service.get_top_opportunities(
            default_stocks, AssetType.STOCK, limit=5
        )
        top_stocks = [
            _create_opportunity(i + 1, score)
            for i, score in enumerate(stock_scores)
        ]
        
        etf_scores = await momentum_service.get_top_opportunities(
            default_etfs, AssetType.ETF, limit=5
        )
        top_etfs = [
            _create_opportunity(i + 1, score)
            for i, score in enumerate(etf_scores)
        ]

    # Market sentiment
    market_sentiment = await sentiment_service.get_market_sentiment()

    # Determine data_source
    ds = "live"
    if use_advanced and hasattr(algorithm, 'data_source') and algorithm.data_source == "stale":
        ds = "stale"

    return DashboardResponse(
        top_stocks=top_stocks,
        top_etfs=top_etfs,
        top_options=[],  # Options require separate data source
        market_sentiment=market_sentiment,
        data_source=ds,
    )


@router.get("/scan", response_model=List[TopOpportunity])
async def scan_market(
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    signal_filter: Optional[str] = Query(None, description="Filter by signal: BUY, SELL, or HOLD"),
):
    """
    Scan the market for top momentum opportunities using advanced AI algorithm.
    
    This endpoint analyzes 50+ stocks and returns the top opportunities
    ranked by the multi-factor momentum score.
    """
    algorithm = get_momentum_algorithm()
    symbols = get_quick_scan_universe()
    
    all_factors = await algorithm.scan_universe(symbols)
    
    # Apply signal filter if specified
    if signal_filter:
        signal_upper = signal_filter.upper()
        all_factors = [f for f in all_factors if f.signal == signal_upper]
    
    # Create opportunities
    opportunities = [
        _create_opportunity_from_factors(i + 1, factors)
        for i, factors in enumerate(all_factors[:limit])
    ]
    
    return opportunities


@router.get("/analyze/{symbol}")
async def analyze_symbol_advanced(symbol: str):
    """
    Get detailed AI momentum analysis for a single symbol.
    
    Returns comprehensive technical indicators, ML predictions,
    and momentum factors.
    """
    algorithm = get_momentum_algorithm()
    factors = await algorithm.analyze_symbol(symbol.upper())
    
    if factors is None:
        raise HTTPException(status_code=404, detail=f"Could not analyze symbol: {symbol}")
    
    # Return detailed analysis
    return {
        "symbol": factors.symbol,
        "signal": factors.signal,
        "composite_score": round(factors.composite_score, 4),
        "price": round(factors.price, 2),
        "price_change": round(factors.price_change, 2),
        
        "momentum": {
            "roc_5d": round(factors.roc_5d, 2),
            "roc_10d": round(factors.roc_10d, 2),
            "roc_20d": round(factors.roc_20d, 2),
            "roc_60d": round(factors.roc_60d, 2),
            "trend_score": round(factors.trend_score, 4),
        },
        
        "volume": {
            "ratio": round(factors.volume_ratio, 2),
            "trend": round(factors.volume_trend, 2),
            "accumulation": round(factors.accumulation, 4),
        },
        
        "technicals": {
            "rsi_14": round(factors.technicals.rsi_14, 2),
            "rsi_7": round(factors.technicals.rsi_7, 2),
            "macd_signal": round(factors.technicals.macd_signal, 4),
            "macd_histogram": round(factors.technicals.macd_histogram, 4),
            "bb_position": round(factors.technicals.bb_position, 2),
            "adx": round(factors.technicals.adx, 2),
            "atr_percent": round(factors.technicals.atr_percent, 2),
            "sma_20_distance": round(factors.technicals.sma_20_distance, 2),
            "sma_50_distance": round(factors.technicals.sma_50_distance, 2),
            "sma_200_distance": round(factors.technicals.sma_200_distance, 2),
            "ema_crossover": round(factors.technicals.ema_crossover, 2),
            "obv_trend": round(factors.technicals.obv_trend, 4),
            "mfi": round(factors.technicals.mfi, 2),
            "stochastic_k": round(factors.technicals.stoch_k, 2),
            "stochastic_d": round(factors.technicals.stoch_d, 2),
        },
        
        "ai_prediction": {
            "score": round(factors.ml_prediction, 4),
            "confidence": round(factors.ml_confidence, 4),
        },
        
        "risk": {
            "volatility_score": round(factors.volatility_score, 4),
        },
        
        "timestamp": factors.timestamp.isoformat(),
    }


@router.get("/stocks", response_model=List[MomentumScore])
async def get_stock_momentum(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
):
    """
    Get momentum scores for specific stocks.
    
    Args:
        symbols: Comma-separated ticker symbols (e.g., "AAPL,MSFT,GOOGL")
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    momentum_service = get_momentum_service()
    return await momentum_service.get_top_opportunities(
        symbol_list, AssetType.STOCK, limit=50
    )


@router.get("/symbol/{symbol}", response_model=MomentumScore)
async def get_symbol_momentum(
    symbol: str,
    asset_type: AssetType = Query(AssetType.STOCK),
):
    """
    Get detailed momentum analysis for a single symbol.
    
    Args:
        symbol: Ticker symbol
        asset_type: Type of asset (stock, etf, option, future)
    """
    momentum_service = get_momentum_service()
    try:
        return await momentum_service.get_momentum_score(symbol.upper(), asset_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# Backtesting Endpoints
# ============================================================================

@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """
    Run a backtest of the momentum strategy.
    
    Simulates trading based on momentum signals over historical data.
    Returns comprehensive performance metrics, trade history, and equity curve.
    
    Example request:
    ```json
    {
        "symbols": ["AAPL", "MSFT", "GOOGL", "NVDA"],
        "start_date": "2023-01-01",
        "end_date": "2024-01-01",
        "initial_capital": 100000,
        "position_size_pct": 0.1,
        "max_positions": 5,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15
    }
    ```
    """
    try:
        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        if start_date >= end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        if (end_date - start_date).days < 30:
            raise HTTPException(status_code=400, detail="Backtest period must be at least 30 days")
        
        if (end_date - start_date).days > 1825:  # 5 years
            raise HTTPException(status_code=400, detail="Backtest period cannot exceed 5 years")
        
        # Create config
        config = BacktestConfig(
            symbols=request.symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            position_size_pct=request.position_size_pct,
            max_positions=request.max_positions,
            stop_loss_pct=request.stop_loss_pct,
            take_profit_pct=request.take_profit_pct,
            momentum_buy_threshold=request.momentum_buy_threshold,
            momentum_sell_threshold=request.momentum_sell_threshold,
            rebalance_frequency=request.rebalance_frequency,
        )
        
        # Run backtest
        engine = get_backtesting_engine()
        results = await engine.run_backtest(config)
        
        # Convert trades
        trade_results = [
            TradeResult(
                symbol=t.symbol,
                action=t.action.value,
                entry_date=t.entry_date,
                entry_price=round(t.entry_price, 2),
                exit_date=t.exit_date,
                exit_price=round(t.exit_price, 2) if t.exit_price else None,
                shares=round(t.shares, 4),
                pnl=round(t.pnl, 2),
                pnl_percent=round(t.pnl_percent, 2),
                holding_days=t.holding_days,
                exit_reason=t.exit_reason,
            )
            for t in results.trades
        ]
        
        # Convert daily snapshots
        snapshot_results = [
            DailySnapshotResult(
                date=s.date,
                portfolio_value=round(s.portfolio_value, 2),
                cash=round(s.cash, 2),
                positions_value=round(s.positions_value, 2),
                daily_return=round(s.daily_return, 6),
                cumulative_return=round(s.cumulative_return, 6),
                drawdown=round(s.drawdown, 6),
                num_positions=s.num_positions,
            )
            for s in results.daily_snapshots
        ]
        
        # Extract equity curve
        equity_curve = [round(s.portfolio_value, 2) for s in results.daily_snapshots]
        dates = [s.date.strftime("%Y-%m-%d") for s in results.daily_snapshots]
        
        return BacktestResponse(
            total_return=round(results.total_return * 100, 2),
            annualized_return=round(results.annualized_return * 100, 2),
            sharpe_ratio=round(results.sharpe_ratio, 2),
            sortino_ratio=round(results.sortino_ratio, 2),
            max_drawdown=round(results.max_drawdown * 100, 2),
            total_trades=results.total_trades,
            winning_trades=results.winning_trades,
            losing_trades=results.losing_trades,
            win_rate=round(results.win_rate * 100, 2),
            profit_factor=round(results.profit_factor, 2),
            avg_trade_return=round(results.avg_trade_return, 2),
            avg_holding_days=round(results.avg_holding_days, 1),
            benchmark_return=round(results.benchmark_return * 100, 2),
            alpha=round(results.alpha * 100, 2),
            start_date=results.start_date,
            end_date=results.end_date,
            trading_days=results.trading_days,
            trades=trade_results,
            daily_snapshots=snapshot_results,
            equity_curve=equity_curve,
            dates=dates,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/backtest/presets")
async def get_backtest_presets():
    """
    Get predefined backtest configurations.
    
    Returns common strategy presets for quick testing.
    """
    return {
        "presets": [
            {
                "name": "Conservative",
                "description": "Lower risk with smaller positions and tighter stops",
                "config": {
                    "position_size_pct": 0.05,
                    "max_positions": 15,
                    "stop_loss_pct": 0.03,
                    "take_profit_pct": 0.10,
                    "momentum_buy_threshold": 0.20,
                    "momentum_sell_threshold": -0.15,
                    "rebalance_frequency": 7,
                }
            },
            {
                "name": "Moderate",
                "description": "Balanced risk/reward settings",
                "config": {
                    "position_size_pct": 0.10,
                    "max_positions": 10,
                    "stop_loss_pct": 0.05,
                    "take_profit_pct": 0.15,
                    "momentum_buy_threshold": 0.15,
                    "momentum_sell_threshold": -0.10,
                    "rebalance_frequency": 5,
                }
            },
            {
                "name": "Aggressive",
                "description": "Higher risk with larger positions and wider stops",
                "config": {
                    "position_size_pct": 0.15,
                    "max_positions": 7,
                    "stop_loss_pct": 0.08,
                    "take_profit_pct": 0.25,
                    "momentum_buy_threshold": 0.10,
                    "momentum_sell_threshold": -0.08,
                    "rebalance_frequency": 3,
                }
            },
            {
                "name": "Swing Trading",
                "description": "Longer holding periods with trend following",
                "config": {
                    "position_size_pct": 0.10,
                    "max_positions": 8,
                    "stop_loss_pct": 0.07,
                    "take_profit_pct": 0.20,
                    "momentum_buy_threshold": 0.18,
                    "momentum_sell_threshold": -0.12,
                    "rebalance_frequency": 10,
                }
            },
        ],
        "suggested_symbols": {
            "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AMD", "TSLA", "NFLX", "CRM"],
            "diversified": ["AAPL", "JPM", "JNJ", "XOM", "PG", "UNH", "V", "HD", "MA", "PFE"],
            "high_momentum": ["NVDA", "AMD", "TSLA", "META", "NFLX", "COIN", "PLTR", "SNOW", "NET", "DDOG"],
            "etfs": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY"],
        }
    }


# ============================================================================
# Max Risk Momentum Endpoints
# ============================================================================

def _factors_to_max_risk_result(factors: MaxRiskFactors) -> MaxRiskScoreResult:
    """Convert MaxRiskFactors dataclass to Pydantic schema."""
    return MaxRiskScoreResult(
        symbol=factors.symbol,
        rank=factors.rank,
        price=factors.price,
        r1w=factors.r1w,
        r1m=factors.r1m,
        return_3m=factors.return_3m,
        return_6m=factors.return_6m,
        return_12m=factors.return_12m,
        rs3m=factors.rs3m,
        rs6m=factors.rs6m,
        rs12m=factors.rs12m,
        vexp=factors.vexp,
        breakout_factor=factors.breakout_factor,
        is_20d_high=factors.is_20d_high,
        vol_accel=factors.vol_accel,
        sma_50=factors.sma_50,
        sma_200=factors.sma_200,
        price_to_200dma=factors.price_to_200dma,
        max_risk_score=factors.max_risk_score,
        turbo_score=factors.turbo_score,
        below_50dma=factors.below_50dma,
        stop_price=factors.stop_price,
        signal=factors.signal,
        timestamp=factors.timestamp,
    )


def _regime_data_to_result(regime: RegimeData) -> MaxRiskRegimeResult:
    """Convert RegimeData dataclass to Pydantic schema."""
    return MaxRiskRegimeResult(
        risk_on=regime.risk_on,
        qqq_close=regime.qqq_close,
        qqq_200sma=regime.qqq_200sma,
        qqq_distance_pct=regime.qqq_distance_pct,
        spy_close=regime.spy_close,
        spy_200sma=regime.spy_200sma,
        description=regime.description,
    )


@router.get("/max-risk-scan", response_model=List[MaxRiskScoreResult])
async def max_risk_scan(
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    use_turbo: bool = Query(False, description="Rank by TurboScore instead of MaxRiskScore"),
):
    """
    Scan the market using the Max Risk Momentum formula (v2).

    MaxRiskMomentum = 0.18*R1W + 0.18*R1M + 0.18*R3M + 0.18*R6M + 0.08*R12M
                    + 0.10*RS3M + 0.06*RS6M + 0.04*RS12M
                    + 0.06*VExp + 0.05*BO + 0.03*VolAccel

    Turbo: + 0.05*(R1M - R3M)
    """
    engine = get_max_risk_engine()
    symbols = get_quick_scan_universe()

    all_factors = await engine.scan_universe(symbols)

    if use_turbo:
        all_factors.sort(key=lambda f: f.turbo_score, reverse=True)
    else:
        all_factors.sort(key=lambda f: f.max_risk_score, reverse=True)

    for i, f in enumerate(all_factors):
        f.rank = i + 1

    return [_factors_to_max_risk_result(f) for f in all_factors[:limit]]


@router.get("/max-risk-portfolio", response_model=MaxRiskPortfolioResponse)
async def max_risk_portfolio(
    top_n: int = Query(10, ge=1, le=20, description="Number of top picks"),
    use_turbo: bool = Query(False, description="Use TurboScore for ranking"),
):
    """
    Get the Max Risk momentum portfolio with QQQ regime filter.

    Regime: RiskOn = QQQ_Close > QQQ_200SMA.
    If RiskOff, all signals become HOLD (cash mode).

    Selection:
    - Scan full universe, price > $5, avg daily $ vol > $50M
    - Rank by 11-factor MaxRiskScore (or Turbo)
    - Top N equal-weight picks
    - Exit: close < 50DMA, or -15% hard stop
    """
    engine = get_max_risk_engine()
    symbols = get_quick_scan_universe()

    regime = await engine.assess_regime()
    top_picks = await engine.get_top_picks(symbols, top_n=top_n, use_turbo=use_turbo)
    all_factors = await engine.scan_universe(symbols)

    if use_turbo:
        all_factors.sort(key=lambda f: f.turbo_score, reverse=True)

    for i, f in enumerate(all_factors):
        f.rank = i + 1

    # If risk-off, override all signals to HOLD
    if not regime.risk_on:
        for f in top_picks:
            f.signal = "HOLD"
        for f in all_factors:
            if f.below_50dma:
                f.signal = "SELL"
            else:
                f.signal = "HOLD"

    return MaxRiskPortfolioResponse(
        top_picks=[_factors_to_max_risk_result(f) for f in top_picks],
        full_ranking=[_factors_to_max_risk_result(f) for f in all_factors[:30]],
        regime=_regime_data_to_result(regime),
        use_turbo=use_turbo,
        total_scanned=len(all_factors),
        data_source=engine.data_source,
    )


@router.get("/max-risk-analyze/{symbol}", response_model=MaxRiskScoreResult)
async def max_risk_analyze_symbol(symbol: str):
    """
    Get Max Risk Momentum analysis for a single symbol.
    """
    engine = get_max_risk_engine()
    factors = await engine.analyze_single(symbol.upper())

    if factors is None:
        raise HTTPException(status_code=404, detail=f"Could not analyze symbol: {symbol}")

    factors.rank = 1
    return _factors_to_max_risk_result(factors)


# ============================================================================
# Institutional Momentum Endpoints
# ============================================================================

def _factors_to_institutional_result(factors: InstitutionalFactors) -> InstitutionalMomentumResult:
    """Convert InstitutionalFactors dataclass to Pydantic schema."""
    return InstitutionalMomentumResult(
        symbol=factors.symbol,
        rank=factors.rank,
        quintile=factors.quintile,
        price=factors.price,
        r12_skip1=round(factors.r12_skip1, 2),
        r6_skip1=round(factors.r6_skip1, 2),
        r3_skip1=round(factors.r3_skip1, 2),
        r1=round(factors.r1, 2),
        volatility=round(factors.volatility, 2),
        risk_adj_return=round(factors.risk_adj_return, 2),
        vol_scaled_weight=round(factors.vol_scaled_weight, 4),
        raw_score=round(factors.raw_score, 4),
        vol_adjusted_score=round(factors.vol_adjusted_score, 4),
        avg_dollar_volume=round(factors.avg_dollar_volume, 0),
        passes_liquidity=factors.passes_liquidity,
        above_200dma=factors.above_200dma,
        distance_to_200dma=round(factors.distance_to_200dma, 2),
        signal=factors.signal,
        timestamp=factors.timestamp,
    )


def _regime_to_result(regime: MarketRegimeData) -> MarketRegimeResult:
    """Convert MarketRegimeData dataclass to Pydantic schema."""
    return MarketRegimeResult(
        regime=regime.regime.value,
        spy_above_200dma=regime.spy_above_200dma,
        spy_distance_200dma=round(regime.spy_distance_200dma, 2),
        market_volatility=round(regime.market_volatility, 2),
        breadth=round(regime.breadth, 2),
        description=regime.description,
    )


@router.get("/institutional-scan", response_model=List[InstitutionalMomentumResult])
async def institutional_scan(
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    vol_adjusted: bool = Query(True, description="Rank by vol-adjusted score"),
):
    """
    Scan the market using institutional momentum scoring.

    Score = 0.4·R(12-1) + 0.3·R(6-1) + 0.2·R(3-1) + 0.1·(R/σ × 10)

    Uses skip-month returns to avoid short-term reversal,
    with optional volatility scaling for equal-risk contribution.
    """
    engine = get_institutional_engine()
    symbols = get_quick_scan_universe()

    all_factors = await engine.scan_universe(symbols)

    if vol_adjusted:
        all_factors.sort(key=lambda f: f.vol_adjusted_score, reverse=True)
    else:
        all_factors.sort(key=lambda f: f.raw_score, reverse=True)

    for i, f in enumerate(all_factors):
        f.rank = i + 1

    return [_factors_to_institutional_result(f) for f in all_factors[:limit]]


@router.get("/institutional-portfolio", response_model=InstitutionalPortfolioResponse)
async def institutional_portfolio(
    top_n: int = Query(10, ge=1, le=30, description="Number of portfolio holdings"),
    vol_scaling: bool = Query(True, description="Use inverse-volatility weighting"),
):
    """
    Build an institutional momentum portfolio.

    Selection:
    - Scan full universe with skip-month momentum
    - Filter: avg daily $ volume ≥ $50M, above 200DMA
    - Rank by vol-adjusted score
    - Weight by inverse volatility (1/σ)
    - Market regime overlay: reduce exposure in BEAR regime

    Returns top N holdings plus full ranking and market regime info.
    """
    engine = get_institutional_engine()
    symbols = get_quick_scan_universe()

    portfolio, regime, _ = await engine.get_portfolio(
        symbols, top_n=top_n, use_vol_scaling=vol_scaling
    )

    all_factors = await engine.scan_universe(symbols)
    all_factors.sort(key=lambda f: f.vol_adjusted_score, reverse=True)
    for i, f in enumerate(all_factors):
        f.rank = i + 1

    breadth = sum(1 for f in all_factors if f.above_200dma) / max(len(all_factors), 1) * 100

    return InstitutionalPortfolioResponse(
        portfolio=[_factors_to_institutional_result(f) for f in portfolio],
        full_ranking=[_factors_to_institutional_result(f) for f in all_factors[:30]],
        market_regime=_regime_to_result(regime),
        breadth=round(breadth, 1),
        vol_scaling_enabled=vol_scaling,
        total_scanned=len(all_factors),
        data_source=engine.data_source,
    )


@router.get("/institutional-analyze/{symbol}", response_model=InstitutionalMomentumResult)
async def institutional_analyze_symbol(symbol: str):
    """
    Get institutional momentum analysis for a single symbol.
    """
    engine = get_institutional_engine()
    factors = await engine.analyze_single(symbol.upper())

    if factors is None:
        raise HTTPException(status_code=404, detail=f"Could not analyze symbol: {symbol}")

    factors.rank = 1
    return _factors_to_institutional_result(factors)


# ============================================================================
# Market Cap Momentum Endpoints
# ============================================================================

@router.get("/market-cap-momentum", response_model=MarketCapMomentumResponse)
async def market_cap_momentum(
    top_n: int = Query(5, ge=1, le=20, description="Top N opportunities per tier"),
):
    """
    Scan the market grouped by market cap tier.

    Uses the same advanced momentum algorithm across 5 tiers:
    Mega (>$476.85B), Large ($81.98B-$476.85B), Medium ($13.73B-$81.98B),
    Small ($3.50B-$13.73B), Micro (<$3.50B).

    Scans all 5 tiers concurrently for speed.
    """
    import math

    algorithm = get_momentum_algorithm()
    mc_service = get_market_cap_service()

    # Snapshot mock symbols before scan so we detect only new mocks from this request
    mock_before = set(algorithm._mock_symbols) if hasattr(algorithm, "_mock_symbols") else set()

    # 1. Collect all seed symbols across tiers (deduplicated)
    all_symbols_set: set = set()
    for tier in TIER_ORDER:
        all_symbols_set.update(mc_service.get_symbols_for_tier(tier))
    all_symbols = sorted(all_symbols_set)

    # 2. Scan entire universe once (instead of 5 separate scans)
    all_factors = await algorithm.scan_universe(all_symbols)

    # Filter out NaN scores (delisted/broken symbols)
    all_factors = [f for f in all_factors if not math.isnan(f.composite_score)]

    # 3. Classify each symbol by actual market cap and bucket into tiers
    tier_buckets: Dict[MarketCapTier, list] = {t: [] for t in TIER_ORDER}
    for f in all_factors:
        mc_val = mc_service._get_market_cap(f.symbol)
        if mc_val is None:
            continue
        tier = mc_service.classify_symbol(f.symbol)
        if tier is not None:
            tier_buckets[tier].append((f, mc_val))

    # 4. Build categories: sort by score descending, take top N
    returned_symbols: List[str] = []
    categories_list: List[MarketCapCategory] = []

    for tier in TIER_ORDER:
        bucket = tier_buckets[tier]
        bucket.sort(key=lambda x: x[0].composite_score, reverse=True)
        top_entries = bucket[:top_n]

        opportunities = []
        for i, (f, mc_val) in enumerate(top_entries):
            opp = _create_opportunity_from_factors(i + 1, f)
            opp.market_cap = mc_val
            opportunities.append(opp)

        returned_symbols.extend(f.symbol for f, _ in top_entries)
        categories_list.append(MarketCapCategory(
            tier=tier.value,
            label=TIER_LABELS[tier],
            opportunities=opportunities,
            total_scanned=len(bucket),
        ))

    # Only stale if returned symbols were newly mocked during THIS scan
    new_mocks = (algorithm._mock_symbols - mock_before) if hasattr(algorithm, "_mock_symbols") else set()
    ds = "stale" if new_mocks & set(returned_symbols) else "live"

    return MarketCapMomentumResponse(
        categories=categories_list,
        data_source=ds,
    )


# ============================================================================
# Market Sentiment Endpoints
# ============================================================================

def _sentiment_metric_to_detail(m: SentimentMetric) -> SentimentMetricDetail:
    """Convert engine SentimentMetric to schema SentimentMetricDetail."""
    return SentimentMetricDetail(
        name=m.name,
        raw_value=round(m.raw_value, 4),
        z_score=round(m.z_score, 4),
        weight=round(m.weight, 4),
        weighted_z=round(m.weighted_z, 4),
        description=m.description,
        series=[round(v, 4) for v in m.series],
    )


def _sentiment_result_to_response(r: SentimentResult) -> MarketSentimentResponse:
    """Convert engine SentimentResult to schema MarketSentimentResponse."""
    return MarketSentimentResponse(
        final_score=round(r.final_score, 4),
        regime=r.regime,
        trend_direction=r.trend_direction,
        trend_slope=round(r.trend_slope, 6),
        composite_raw=round(r.composite_raw, 4),
        metrics=[_sentiment_metric_to_detail(m) for m in r.metrics],
        window_size=r.window_size,
        timestamp=r.timestamp,
        data_source=r.data_source,
    )


@router.get("/market-sentiment", response_model=MarketSentimentResponse)
async def market_sentiment(
    window: int = Query(20, ge=5, le=60, description="Rolling window W in trading days"),
):
    """
    Market Sentiment model — single rolling W-day window.

    Computes 9 metrics strictly within one W-day window:
    1. Implied vs Realized Volatility Spread
    2. 25-delta Put-Call Skew
    3. Put/Call Volume Ratio
    4. Net Option Delta Flow / Avg Volume
    5. % Stocks above W-period Moving Average
    6. Advance-Decline Ratio
    7. Price Acceleration (W/2 vs W)
    8. Volume-Weighted Momentum
    9. ATR Compression Ratio

    Each metric Z-scored within W → weighted aggregation → logistic → 0-1 score.
    Outputs: FinalScore, Regime, Trend direction.
    """
    engine = get_sentiment_engine(window=window)
    result = await engine.compute()
    return _sentiment_result_to_response(result)
