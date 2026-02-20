"""
TrendEdge Backend - Backtesting Service

Historical simulation engine to test momentum algorithm performance.
Supports configurable date ranges, position sizing, and risk management.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from app.services.advanced_momentum import AdvancedMomentumAlgorithm, TechnicalIndicators


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Trade:
    """Represents a single trade."""
    symbol: str
    action: TradeAction
    entry_date: datetime
    entry_price: float
    shares: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    holding_days: int = 0
    exit_reason: str = ""


@dataclass
class DailySnapshot:
    """Daily portfolio snapshot."""
    date: datetime
    portfolio_value: float
    cash: float
    positions_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    num_positions: int


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    position_size_pct: float = 0.1  # 10% per position
    max_positions: int = 10
    stop_loss_pct: float = 0.05  # 5% stop loss
    take_profit_pct: float = 0.15  # 15% take profit
    momentum_buy_threshold: float = 0.15
    momentum_sell_threshold: float = -0.10
    rebalance_frequency: int = 5  # Days between rebalancing
    commission_pct: float = 0.001  # 0.1% commission


@dataclass
class BacktestResults:
    """Results from a backtest run."""
    config: BacktestConfig
    trades: List[Trade]
    daily_snapshots: List[DailySnapshot]
    
    # Performance metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_holding_days: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Benchmark comparison
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    
    # Time info
    start_date: datetime = None
    end_date: datetime = None
    trading_days: int = 0


class BacktestingEngine:
    """
    Backtesting engine for momentum strategy.
    
    Simulates trading based on momentum signals over historical data.
    """
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.momentum_algo = AdvancedMomentumAlgorithm()
        self._price_cache: Dict[str, pd.DataFrame] = {}
    
    def _fetch_historical_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """Fetch historical price data."""
        cache_key = f"{symbol}_{start_date.date()}_{end_date.date()}"
        
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
        
        try:
            # Add buffer for technical indicator calculation
            buffer_start = start_date - timedelta(days=200)
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=buffer_start, end=end_date)
            
            if hist.empty or len(hist) < 50:
                # Generate mock data for testing
                hist = self._generate_mock_historical(symbol, buffer_start, end_date)
            
            self._price_cache[cache_key] = hist
            return hist
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return self._generate_mock_historical(symbol, start_date - timedelta(days=200), end_date)
    
    def _generate_mock_historical(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> pd.DataFrame:
        """Generate realistic mock historical data."""
        np.random.seed(hash(symbol) % 2**32)
        
        # Base prices for known symbols
        base_prices = {
            "AAPL": 150, "MSFT": 350, "GOOGL": 140, "AMZN": 150, "NVDA": 500,
            "META": 350, "TSLA": 200, "AMD": 120, "NFLX": 450, "SPY": 450,
        }
        base_price = base_prices.get(symbol, 100 + np.random.random() * 200)
        
        # Generate daily data
        dates = pd.date_range(start=start_date, end=end_date, freq='B')  # Business days
        n_days = len(dates)
        
        # Random walk with momentum regime changes
        drift = 0.0003
        volatility = 0.02
        
        # Add regime changes
        regime_changes = np.random.choice([0, 1], size=n_days, p=[0.95, 0.05])
        regime = np.cumsum(regime_changes) % 3  # 0=bull, 1=bear, 2=sideways
        
        drift_by_regime = {0: 0.001, 1: -0.0005, 2: 0.0001}
        daily_drift = np.array([drift_by_regime[r] for r in regime])
        
        returns = np.random.normal(daily_drift, volatility, n_days)
        prices = base_price * np.cumprod(1 + returns)
        
        # Generate OHLCV
        high = prices * (1 + np.abs(np.random.normal(0.01, 0.005, n_days)))
        low = prices * (1 - np.abs(np.random.normal(0.01, 0.005, n_days)))
        open_prices = prices * (1 + np.random.normal(0, 0.005, n_days))
        volume = np.random.uniform(5e6, 50e6, n_days)
        
        df = pd.DataFrame({
            'Open': open_prices,
            'High': high,
            'Low': low,
            'Close': prices,
            'Volume': volume,
        }, index=dates)
        
        return df
    
    def _calculate_momentum_signal(
        self, 
        hist: pd.DataFrame, 
        date_idx: int
    ) -> Tuple[float, str, float]:
        """
        Calculate momentum signal for a specific date.
        Returns: (score, signal, confidence)
        """
        if date_idx < 60:  # Need enough history
            return 0.0, "HOLD", 0.0
        
        # Get data up to this date
        data = hist.iloc[:date_idx + 1].copy()
        
        if len(data) < 60:
            return 0.0, "HOLD", 0.0
        
        close = data['Close']
        high = data['High']
        low = data['Low']
        volume = data['Volume']
        
        # Calculate indicators
        # ROC
        roc_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) > 5 else 0
        roc_10d = (close.iloc[-1] - close.iloc[-10]) / close.iloc[-10] * 100 if len(close) > 10 else 0
        roc_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100 if len(close) > 20 else 0
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        rsi_14 = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50
        
        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9).mean()
        macd_hist = macd.iloc[-1] - macd_signal.iloc[-1]
        
        # Volume ratio
        vol_avg = volume.rolling(20).mean()
        vol_ratio = volume.iloc[-1] / vol_avg.iloc[-1] if vol_avg.iloc[-1] > 0 else 1.0
        
        # SMA distances
        sma_20 = close.rolling(20).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_20_dist = (close.iloc[-1] - sma_20) / sma_20 * 100
        sma_50_dist = (close.iloc[-1] - sma_50) / sma_50 * 100 if len(close) >= 50 else 0
        
        # Composite score
        price_momentum = (roc_5d * 0.3 + roc_10d * 0.4 + roc_20d * 0.3) / 20
        price_momentum = np.clip(price_momentum, -1, 1)
        
        # RSI component (oversold = bullish, overbought = bearish)
        rsi_score = (50 - rsi_14) / 50 * 0.3
        
        # MACD component
        macd_score = np.clip(macd_hist / 5, -0.3, 0.3)
        
        # Volume component
        vol_score = (vol_ratio - 1) * 0.2 if price_momentum > 0 else -(vol_ratio - 1) * 0.2
        vol_score = np.clip(vol_score, -0.2, 0.2)
        
        # Trend component
        trend_score = 0
        if sma_20_dist > 0 and sma_50_dist > 0:
            trend_score = 0.2
        elif sma_20_dist < 0 and sma_50_dist < 0:
            trend_score = -0.2
        
        # Composite
        composite = (
            price_momentum * 0.35 +
            rsi_score * 0.15 +
            macd_score * 0.20 +
            vol_score * 0.15 +
            trend_score * 0.15
        )
        composite = np.clip(composite, -1, 1)
        
        # Determine signal
        if composite > 0.15:
            signal = "BUY"
        elif composite < -0.10:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Confidence based on indicator agreement
        bullish_signals = sum([
            roc_10d > 0,
            rsi_14 < 70,
            macd_hist > 0,
            sma_20_dist > 0,
            vol_ratio > 1.0 if price_momentum > 0 else vol_ratio < 1.0
        ])
        confidence = bullish_signals / 5 if signal == "BUY" else (5 - bullish_signals) / 5 if signal == "SELL" else 0.5
        
        return composite, signal, confidence
    
    async def run_backtest(self, config: BacktestConfig) -> BacktestResults:
        """Run a complete backtest simulation."""
        
        # Fetch all historical data
        loop = asyncio.get_event_loop()
        
        historical_data: Dict[str, pd.DataFrame] = {}
        for symbol in config.symbols:
            data = await loop.run_in_executor(
                self.executor,
                self._fetch_historical_data,
                symbol,
                config.start_date,
                config.end_date
            )
            if data is not None and not data.empty:
                historical_data[symbol] = data
        
        if not historical_data:
            raise ValueError("No historical data available for backtesting")
        
        # Get common trading dates
        all_dates = set()
        for df in historical_data.values():
            all_dates.update(df.index.tolist())
        
        trading_dates = sorted([
            d for d in all_dates 
            if config.start_date <= d.to_pydatetime().replace(tzinfo=None) <= config.end_date
        ])
        
        # Initialize portfolio
        cash = config.initial_capital
        positions: Dict[str, Trade] = {}  # symbol -> Trade
        trades: List[Trade] = []
        daily_snapshots: List[DailySnapshot] = []
        peak_value = config.initial_capital
        last_rebalance = 0
        
        # Run simulation
        for day_idx, date in enumerate(trading_dates):
            date_dt = date.to_pydatetime().replace(tzinfo=None) if hasattr(date, 'to_pydatetime') else date
            
            # Calculate current portfolio value
            positions_value = 0.0
            for symbol, trade in positions.items():
                if symbol in historical_data:
                    df = historical_data[symbol]
                    if date in df.index:
                        current_price = df.loc[date, 'Close']
                        positions_value += trade.shares * current_price
            
            portfolio_value = cash + positions_value
            
            # Check stop loss and take profit
            closed_positions = []
            for symbol, trade in positions.items():
                if symbol in historical_data:
                    df = historical_data[symbol]
                    if date in df.index:
                        current_price = df.loc[date, 'Close']
                        pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                        
                        # Stop loss
                        if pnl_pct <= -config.stop_loss_pct:
                            trade.exit_date = date_dt
                            trade.exit_price = current_price
                            trade.pnl = (current_price - trade.entry_price) * trade.shares
                            trade.pnl_percent = pnl_pct * 100
                            trade.holding_days = (date_dt - trade.entry_date).days
                            trade.exit_reason = "Stop Loss"
                            
                            cash += trade.shares * current_price * (1 - config.commission_pct)
                            trades.append(trade)
                            closed_positions.append(symbol)
                        
                        # Take profit
                        elif pnl_pct >= config.take_profit_pct:
                            trade.exit_date = date_dt
                            trade.exit_price = current_price
                            trade.pnl = (current_price - trade.entry_price) * trade.shares
                            trade.pnl_percent = pnl_pct * 100
                            trade.holding_days = (date_dt - trade.entry_date).days
                            trade.exit_reason = "Take Profit"
                            
                            cash += trade.shares * current_price * (1 - config.commission_pct)
                            trades.append(trade)
                            closed_positions.append(symbol)
            
            for symbol in closed_positions:
                del positions[symbol]
            
            # Rebalance check
            should_rebalance = (day_idx - last_rebalance) >= config.rebalance_frequency
            
            if should_rebalance:
                last_rebalance = day_idx
                
                # Calculate signals for all symbols
                signals: List[Tuple[str, float, str, float]] = []
                
                for symbol in config.symbols:
                    if symbol not in historical_data:
                        continue
                    
                    df = historical_data[symbol]
                    if date not in df.index:
                        continue
                    
                    # Find index of current date
                    date_list = df.index.tolist()
                    try:
                        idx = date_list.index(date)
                    except ValueError:
                        continue
                    
                    score, signal, confidence = self._calculate_momentum_signal(df, idx)
                    signals.append((symbol, score, signal, confidence))
                
                # Sort by score (best opportunities first)
                signals.sort(key=lambda x: x[1], reverse=True)
                
                # Sell positions that turned bearish
                for symbol, trade in list(positions.items()):
                    symbol_signal = next((s for s in signals if s[0] == symbol), None)
                    
                    if symbol_signal and symbol_signal[2] == "SELL":
                        if symbol in historical_data and date in historical_data[symbol].index:
                            current_price = historical_data[symbol].loc[date, 'Close']
                            
                            trade.exit_date = date_dt
                            trade.exit_price = current_price
                            trade.pnl = (current_price - trade.entry_price) * trade.shares
                            trade.pnl_percent = ((current_price - trade.entry_price) / trade.entry_price) * 100
                            trade.holding_days = (date_dt - trade.entry_date).days
                            trade.exit_reason = "Sell Signal"
                            
                            cash += trade.shares * current_price * (1 - config.commission_pct)
                            trades.append(trade)
                            del positions[symbol]
                
                # Buy new positions
                for symbol, score, signal, confidence in signals:
                    if signal != "BUY":
                        continue
                    
                    if symbol in positions:
                        continue
                    
                    if len(positions) >= config.max_positions:
                        break
                    
                    if symbol not in historical_data or date not in historical_data[symbol].index:
                        continue
                    
                    current_price = historical_data[symbol].loc[date, 'Close']
                    position_value = portfolio_value * config.position_size_pct
                    
                    if position_value > cash:
                        position_value = cash * 0.95  # Leave some cash
                    
                    if position_value < 100:  # Minimum position
                        continue
                    
                    shares = position_value / current_price
                    cost = shares * current_price * (1 + config.commission_pct)
                    
                    if cost > cash:
                        continue
                    
                    cash -= cost
                    
                    positions[symbol] = Trade(
                        symbol=symbol,
                        action=TradeAction.BUY,
                        entry_date=date_dt,
                        entry_price=current_price,
                        shares=shares,
                    )
            
            # Calculate daily metrics
            positions_value = sum(
                trade.shares * historical_data[symbol].loc[date, 'Close']
                for symbol, trade in positions.items()
                if symbol in historical_data and date in historical_data[symbol].index
            )
            
            portfolio_value = cash + positions_value
            peak_value = max(peak_value, portfolio_value)
            drawdown = (peak_value - portfolio_value) / peak_value
            
            daily_return = 0.0
            cumulative_return = (portfolio_value - config.initial_capital) / config.initial_capital
            
            if daily_snapshots:
                prev_value = daily_snapshots[-1].portfolio_value
                daily_return = (portfolio_value - prev_value) / prev_value
            
            daily_snapshots.append(DailySnapshot(
                date=date_dt,
                portfolio_value=portfolio_value,
                cash=cash,
                positions_value=positions_value,
                daily_return=daily_return,
                cumulative_return=cumulative_return,
                drawdown=drawdown,
                num_positions=len(positions),
            ))
        
        # Close remaining positions at end
        end_date = trading_dates[-1] if trading_dates else config.end_date
        end_date_dt = end_date.to_pydatetime().replace(tzinfo=None) if hasattr(end_date, 'to_pydatetime') else end_date
        
        for symbol, trade in positions.items():
            if symbol in historical_data and end_date in historical_data[symbol].index:
                current_price = historical_data[symbol].loc[end_date, 'Close']
                
                trade.exit_date = end_date_dt
                trade.exit_price = current_price
                trade.pnl = (current_price - trade.entry_price) * trade.shares
                trade.pnl_percent = ((current_price - trade.entry_price) / trade.entry_price) * 100
                trade.holding_days = (end_date_dt - trade.entry_date).days
                trade.exit_reason = "End of Backtest"
                
                trades.append(trade)
        
        # Calculate final metrics
        results = self._calculate_metrics(config, trades, daily_snapshots, historical_data)
        
        return results
    
    def _calculate_metrics(
        self,
        config: BacktestConfig,
        trades: List[Trade],
        snapshots: List[DailySnapshot],
        historical_data: Dict[str, pd.DataFrame]
    ) -> BacktestResults:
        """Calculate performance metrics."""
        
        results = BacktestResults(
            config=config,
            trades=trades,
            daily_snapshots=snapshots,
            start_date=config.start_date,
            end_date=config.end_date,
            trading_days=len(snapshots),
        )
        
        if not snapshots:
            return results
        
        # Basic returns
        final_value = snapshots[-1].portfolio_value
        results.total_return = (final_value - config.initial_capital) / config.initial_capital
        
        # Annualized return
        years = len(snapshots) / 252
        if years > 0:
            results.annualized_return = (1 + results.total_return) ** (1 / years) - 1
        
        # Daily returns for Sharpe/Sortino
        daily_returns = [s.daily_return for s in snapshots]
        
        if daily_returns and np.std(daily_returns) > 0:
            # Sharpe Ratio (assuming 0% risk-free rate)
            results.sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
            
            # Sortino Ratio (downside deviation)
            negative_returns = [r for r in daily_returns if r < 0]
            if negative_returns:
                downside_std = np.std(negative_returns)
                if downside_std > 0:
                    results.sortino_ratio = np.mean(daily_returns) / downside_std * np.sqrt(252)
        
        # Max Drawdown
        results.max_drawdown = max(s.drawdown for s in snapshots) if snapshots else 0
        
        # Trade statistics
        results.total_trades = len(trades)
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        
        results.winning_trades = len(winning)
        results.losing_trades = len(losing)
        
        if results.total_trades > 0:
            results.win_rate = results.winning_trades / results.total_trades
            results.avg_trade_return = np.mean([t.pnl_percent for t in trades])
            results.avg_holding_days = np.mean([t.holding_days for t in trades])
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        if gross_loss > 0:
            results.profit_factor = gross_profit / gross_loss
        
        # Benchmark comparison (SPY)
        if 'SPY' in historical_data:
            spy_data = historical_data['SPY']
            if len(spy_data) >= 2:
                spy_start = spy_data.iloc[0]['Close']
                spy_end = spy_data.iloc[-1]['Close']
                results.benchmark_return = (spy_end - spy_start) / spy_start
                results.alpha = results.total_return - results.benchmark_return
        
        return results


# Singleton instance
_backtesting_engine: Optional[BacktestingEngine] = None


def get_backtesting_engine() -> BacktestingEngine:
    """Get singleton backtesting engine instance."""
    global _backtesting_engine
    if _backtesting_engine is None:
        _backtesting_engine = BacktestingEngine()
    return _backtesting_engine
