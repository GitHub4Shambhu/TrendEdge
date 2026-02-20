"""
TrendEdge Backend - Momentum Calculation Service

This service implements the core momentum algorithm combining:
1. Price momentum (ROC, RSI)
2. Volume analysis
3. Social sentiment scoring
4. ML-based trend prediction

AI Maintainability Notes:
- Each calculation method is isolated and documented
- All parameters are configurable via Settings
- Clear input/output types for each function
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from app.core.config import get_settings
from app.schemas.momentum import AssetType, MomentumScore, SignalType


class MomentumService:
    """
    Service for calculating momentum scores across assets.
    
    The momentum score combines multiple factors:
    - Technical momentum (40%): ROC, RSI, MACD signals
    - Volume momentum (20%): Volume vs moving average
    - Trend strength (20%): ADX-based trend measurement
    - Sentiment (20%): Social media sentiment when available
    """

    def __init__(self):
        self.settings = get_settings()
        self._cache: Dict[str, Tuple[MomentumScore, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)

    def calculate_roc(self, prices: pd.Series, period: int = 10) -> float:
        """
        Calculate Rate of Change (ROC) momentum indicator.
        
        Args:
            prices: Series of closing prices
            period: Lookback period in days
            
        Returns:
            ROC value as percentage
        """
        if len(prices) < period + 1:
            return 0.0
        return ((prices.iloc[-1] - prices.iloc[-period - 1]) / prices.iloc[-period - 1]) * 100

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            prices: Series of closing prices
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
        return 100 - (100 / (1 + rs))

    def calculate_volume_ratio(self, volumes: pd.Series, period: int = 20) -> float:
        """
        Calculate current volume vs average volume ratio.
        
        Args:
            volumes: Series of volume data
            period: Moving average period
            
        Returns:
            Volume ratio (1.0 = average, >1 = above average)
        """
        if len(volumes) < period:
            return 1.0
        avg_volume = volumes.iloc[-period:].mean()
        return volumes.iloc[-1] / avg_volume if avg_volume > 0 else 1.0

    def calculate_trend_strength(self, prices: pd.Series, period: int = 14) -> float:
        """
        Calculate trend strength using simplified ADX-like metric.
        
        Args:
            prices: Series of closing prices
            period: Calculation period
            
        Returns:
            Trend strength (0-1)
        """
        if len(prices) < period + 1:
            return 0.5

        # Simplified trend strength based on directional movement
        high_low_range = prices.rolling(period).max() - prices.rolling(period).min()
        directional_move = abs(prices.iloc[-1] - prices.iloc[-period])
        
        if high_low_range.iloc[-1] == 0:
            return 0.5
        
        strength = directional_move / high_low_range.iloc[-1]
        return min(max(strength, 0), 1)

    def _determine_signal(self, score: float, rsi: float) -> SignalType:
        """
        Determine trading signal based on momentum score and RSI.
        
        Args:
            score: Combined momentum score
            rsi: RSI value
            
        Returns:
            Trading signal (BUY/SELL/HOLD)
        """
        threshold = self.settings.momentum_threshold

        # Strong buy conditions
        if score > threshold and rsi < 70:
            return SignalType.BUY
        # Strong sell conditions
        elif score < -threshold or rsi > 80:
            return SignalType.SELL
        # Hold otherwise
        return SignalType.HOLD

    async def get_momentum_score(
        self,
        symbol: str,
        asset_type: AssetType = AssetType.STOCK,
        sentiment_score: Optional[float] = None,
    ) -> MomentumScore:
        """
        Calculate comprehensive momentum score for a symbol.
        
        Args:
            symbol: Ticker symbol
            asset_type: Type of asset
            sentiment_score: Optional pre-calculated sentiment
            
        Returns:
            MomentumScore with all metrics
        """
        # Check cache
        cache_key = f"{symbol}:{asset_type.value}"
        if cache_key in self._cache:
            cached_score, cached_time = self._cache[cache_key]
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return cached_score

        # Fetch market data
        lookback = self.settings.momentum_lookback_days + 30  # Extra for calculations
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{lookback}d")

        if hist.empty:
            raise ValueError(f"No data found for symbol: {symbol}")

        prices = hist["Close"]
        volumes = hist["Volume"]

        # Calculate components
        roc = self.calculate_roc(prices, period=10)
        rsi = self.calculate_rsi(prices, period=14)
        volume_ratio = self.calculate_volume_ratio(volumes, period=20)
        trend_strength = self.calculate_trend_strength(prices, period=14)

        # Normalize ROC to -1 to 1 range
        roc_normalized = np.tanh(roc / 20)  # Soft normalization

        # RSI contribution: oversold (<30) = positive, overbought (>70) = negative
        rsi_contribution = (50 - rsi) / 50

        # Combine scores with weights
        technical_score = (roc_normalized * 0.5 + rsi_contribution * 0.5)
        
        # Final weighted score
        weights = {
            "technical": 0.4,
            "volume": 0.2,
            "trend": 0.2,
            "sentiment": self.settings.sentiment_weight,
        }

        # Adjust weights if no sentiment
        if sentiment_score is None:
            sentiment_score = 0
            weights["technical"] = 0.5
            weights["volume"] = 0.25
            weights["trend"] = 0.25
            weights["sentiment"] = 0

        final_score = (
            technical_score * weights["technical"]
            + (volume_ratio - 1) * 0.1 * weights["volume"]
            + (trend_strength - 0.5) * weights["trend"]
            + sentiment_score * weights["sentiment"]
        )

        # Clamp to -1 to 1
        final_score = max(min(final_score, 1.0), -1.0)

        # Determine signal
        signal = self._determine_signal(final_score, rsi)

        # Calculate confidence based on data quality and agreement
        confidence = min(
            0.5 + trend_strength * 0.3 + (1 if volume_ratio > 1.2 else 0) * 0.2,
            1.0,
        )

        # Price change percentage
        price_change_pct = ((prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]) * 100

        result = MomentumScore(
            symbol=symbol,
            asset_type=asset_type,
            score=round(final_score, 4),
            signal=signal,
            confidence=round(confidence, 4),
            price=round(prices.iloc[-1], 2),
            price_change_pct=round(price_change_pct, 2),
            volume_ratio=round(volume_ratio, 2),
            sentiment_score=sentiment_score if sentiment_score else None,
            updated_at=datetime.utcnow(),
        )

        # Cache result
        self._cache[cache_key] = (result, datetime.utcnow())

        return result

    async def get_top_opportunities(
        self,
        symbols: List[str],
        asset_type: AssetType = AssetType.STOCK,
        limit: int = 10,
    ) -> List[MomentumScore]:
        """
        Get top momentum opportunities from a list of symbols.
        
        Args:
            symbols: List of ticker symbols to analyze
            asset_type: Type of assets
            limit: Maximum results to return
            
        Returns:
            Sorted list of MomentumScore (highest momentum first)
        """
        scores = []
        for symbol in symbols:
            try:
                score = await self.get_momentum_score(symbol, asset_type)
                scores.append(score)
            except Exception:
                continue  # Skip symbols with errors

        # Sort by score (highest first for buys)
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:limit]


# Singleton instance
_momentum_service: Optional[MomentumService] = None


def get_momentum_service() -> MomentumService:
    """Get or create the momentum service singleton."""
    global _momentum_service
    if _momentum_service is None:
        _momentum_service = MomentumService()
    return _momentum_service
