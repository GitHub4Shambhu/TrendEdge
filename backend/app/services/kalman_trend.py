"""
TrendEdge Backend - Kalman Filter Adaptive Trend Estimator

Replaces fixed-period moving averages with a Kalman Filter that dynamically
adjusts its gain to separate noise from the true price trend.

State vector:  x = [price_level, price_velocity]
Transition:    x_k = F * x_{k-1}  (constant-velocity model)
Observation:   z_k = H * x_k + noise

Key advantage over SMAs:
- Adapts gain (Kalman Gain) each step: higher weight to observations when
  measurement noise is low, higher weight to prediction when noise is high.
- Produces a smooth latent price trend AND a velocity (first derivative)
  that is a clean, forward-looking momentum signal.
- No look-ahead bias: purely recursive, causal filter.

Output signals:
- kalman_trend:    smoothed price level (replaces SMA)
- kalman_velocity: rate-of-change of the latent trend (momentum proxy)
- kalman_signal:   normalised z-score of velocity → [-1, +1]
- trend_strength:  |velocity| / price × 100 (% per day equivalent)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Core Kalman Filter (pure NumPy, no external dependency)
# ---------------------------------------------------------------------------

class KalmanPriceFilter:
    """
    2-state Kalman Filter: [level, velocity].

    Parameters
    ----------
    process_noise_level    : Q[0,0]  – how much the *true* level can jump per step
    process_noise_velocity : Q[1,1]  – how much the *true* velocity can change per step
    measurement_noise      : R       – variance of the observed price around true level
    """

    def __init__(
        self,
        process_noise_level: float = 1e-4,
        process_noise_velocity: float = 1e-5,
        measurement_noise: float = 1e-2,
    ):
        # State transition: level_{t} = level_{t-1} + velocity_{t-1}
        self.F = np.array([[1.0, 1.0],
                           [0.0, 1.0]])

        # Observation: we only observe the price level
        self.H = np.array([[1.0, 0.0]])

        # Process noise covariance
        self.Q = np.array([[process_noise_level, 0.0],
                           [0.0, process_noise_velocity]])

        # Measurement noise covariance
        self.R = np.array([[measurement_noise]])

        # Initial state & covariance (will be set on first observation)
        self.x: Optional[np.ndarray] = None   # [level, velocity]
        self.P: np.ndarray = np.eye(2) * 1.0  # Initial uncertainty

    def reset(self, initial_price: float) -> None:
        """Reset filter to start fresh from a given price."""
        self.x = np.array([[initial_price], [0.0]])
        self.P = np.eye(2) * 1.0

    def update(self, observed_price: float) -> Tuple[float, float]:
        """
        Process a single new price observation.

        Returns
        -------
        (level, velocity) — the posterior state estimate
        """
        z = np.array([[observed_price]])

        # --- Initialise on first call ---
        if self.x is None:
            self.reset(observed_price)
            return observed_price, 0.0

        # --- Predict step ---
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q

        # --- Update step ---
        S = self.H @ P_pred @ self.H.T + self.R          # Innovation covariance
        K = P_pred @ self.H.T @ np.linalg.inv(S)         # Kalman gain
        innovation = z - self.H @ x_pred
        self.x = x_pred + K @ innovation
        self.P = (np.eye(2) - K @ self.H) @ P_pred

        return float(self.x[0, 0]), float(self.x[1, 0])

    def filter_series(self, prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run the filter over a full price series.

        Returns
        -------
        levels, velocities  – arrays of same length as prices
        """
        self.reset(prices[0])
        levels = np.empty(len(prices))
        velocities = np.empty(len(prices))
        for i, p in enumerate(prices):
            levels[i], velocities[i] = self.update(float(p))
        return levels, velocities


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class KalmanTrendResult:
    """Result of Kalman Filter trend analysis for a single symbol."""
    symbol: str

    # Smoothed price (Kalman level)
    kalman_trend: float = 0.0       # Current latent price level
    kalman_velocity: float = 0.0    # Current latent price velocity ($/day)

    # Normalised signals
    kalman_signal: float = 0.0      # Velocity z-score → [-1, +1]
    trend_strength: float = 0.0     # |velocity| / price * 100 (%)

    # Distance from Kalman trend (mean-reversion signal)
    price_vs_trend_pct: float = 0.0  # (price - kalman_trend) / kalman_trend * 100

    # Trend direction confirmation
    trend_direction: str = "NEUTRAL"  # UP / DOWN / NEUTRAL
    acceleration: float = 0.0         # Change in velocity (2nd derivative)

    # Composite signal
    composite_signal: float = 0.0   # Combined kalman-based trend score [-1, +1]
    signal: str = "HOLD"            # BUY / SELL / HOLD

    # Price context
    price: float = 0.0
    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class KalmanTrendService:
    """
    Computes Kalman Filter–based trend signals for a universe of symbols.

    The filter is fitted per-symbol using ~6 months of daily close prices.
    Noise parameters are auto-scaled to each symbol's historical volatility so
    that a high-vol stock (TSLA) gets wider process noise than a low-vol one.
    """

    # Relative process noise: expressed as fraction of daily-return variance
    _LEVEL_NOISE_FACTOR = 0.5
    _VELOCITY_NOISE_FACTOR = 0.05
    # Measurement noise: fraction of daily-return variance
    _MEASUREMENT_NOISE_FACTOR = 2.0

    # Lookback for noise estimation (trading days)
    _LOOKBACK_DAYS = 126   # ~6 months

    def __init__(self):
        self._cache: Dict[str, Tuple[KalmanTrendResult, datetime]] = {}
        self._cache_ttl_minutes = 10
        self._executor = ThreadPoolExecutor(max_workers=8)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(self, symbol: str) -> KalmanTrendResult:
        """Analyse a single symbol. Uses cache to avoid redundant fetches."""
        if self._is_cached(symbol):
            return self._cache[symbol][0]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._compute, symbol)
        self._cache[symbol] = (result, datetime.utcnow())
        return result

    async def analyze_universe(self, symbols: List[str]) -> List[KalmanTrendResult]:
        """Analyse a universe of symbols in parallel."""
        tasks = [self.analyze(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, KalmanTrendResult)]

    # ------------------------------------------------------------------
    # Internal computation
    # ------------------------------------------------------------------

    def _compute(self, symbol: str) -> KalmanTrendResult:
        """Fetch data and compute Kalman trend result."""
        result = KalmanTrendResult(symbol=symbol)
        try:
            hist = self._fetch_history(symbol)
            if hist is None or len(hist) < 30:
                return result

            closes = hist["Close"].values.astype(float)
            result.price = float(closes[-1])

            # Auto-tune noise parameters to symbol volatility
            returns = np.diff(np.log(closes))
            daily_var = float(np.var(returns)) * (result.price ** 2)  # in price² units

            kf = KalmanPriceFilter(
                process_noise_level=daily_var * self._LEVEL_NOISE_FACTOR,
                process_noise_velocity=daily_var * self._VELOCITY_NOISE_FACTOR,
                measurement_noise=daily_var * self._MEASUREMENT_NOISE_FACTOR,
            )

            levels, velocities = kf.filter_series(closes)

            result.kalman_trend = float(levels[-1])
            result.kalman_velocity = float(velocities[-1])

            # Normalise velocity to [-1, +1] via rolling z-score
            vel_mean = float(np.mean(velocities[-60:]))
            vel_std = float(np.std(velocities[-60:])) + 1e-10
            z = (result.kalman_velocity - vel_mean) / vel_std
            result.kalman_signal = float(np.tanh(z))

            # Trend strength as % of price per day
            result.trend_strength = abs(result.kalman_velocity) / (result.price + 1e-10) * 100

            # Price vs Kalman trend (mean-reversion component)
            result.price_vs_trend_pct = (result.price - result.kalman_trend) / (result.kalman_trend + 1e-10) * 100

            # Acceleration (change in velocity over last 5 days)
            if len(velocities) >= 6:
                result.acceleration = float(velocities[-1] - velocities[-6])

            # Trend direction
            if result.kalman_velocity > vel_std * 0.3:
                result.trend_direction = "UP"
            elif result.kalman_velocity < -vel_std * 0.3:
                result.trend_direction = "DOWN"
            else:
                result.trend_direction = "NEUTRAL"

            # Composite signal: blend velocity signal + price-vs-trend (contrarian dampener)
            mean_rev = float(np.tanh(-result.price_vs_trend_pct / 5.0))  # dampens over-extensions
            result.composite_signal = round(0.7 * result.kalman_signal + 0.3 * mean_rev, 4)

            # Signal generation
            if result.composite_signal > 0.25 and result.trend_direction == "UP":
                result.signal = "BUY"
            elif result.composite_signal < -0.25 and result.trend_direction == "DOWN":
                result.signal = "SELL"
            else:
                result.signal = "HOLD"

            result.data_source = "live"

        except Exception:
            result.data_source = "error"

        return result

    def _fetch_history(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch ~6 months of daily OHLCV history."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d")
            if hist is not None and len(hist) >= 30:
                return hist
        except Exception:
            pass
        return None

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache:
            return False
        cached_at = self._cache[symbol][1]
        elapsed = (datetime.utcnow() - cached_at).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_kalman_service: Optional[KalmanTrendService] = None


def get_kalman_service() -> KalmanTrendService:
    global _kalman_service
    if _kalman_service is None:
        _kalman_service = KalmanTrendService()
    return _kalman_service
