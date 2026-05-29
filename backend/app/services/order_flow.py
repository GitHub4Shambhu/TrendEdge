"""
TrendEdge Backend - Order Flow Imbalance (OFI) Signal

Constructs a proxy for institutional order flow imbalance from OHLCV data
using three complementary microstructure methods:

1. **Tick-rule directional flow** (45% weight):
   sign(close - open) × volume → rolling cumulative buy/sell pressure
   Z-scored over 20-day window.

2. **Amihud liquidity-adjusted flow** (30% weight):
   Volume / (|Δprice| × price) captures flow relative to price impact.
   High illiquidity → large moves per unit volume → stronger signal.

3. **VWAP deviation** (25% weight):
   (close - VWAP) / ATR measures intraday price pressure relative to
   fair value and volatility. Positive = close above VWAP → buyers in control.

Combined: ofi_score = 0.45*tick_z + 0.30*liq_adj_z + 0.25*vwap_dev_z

Additional dynamics:
- ofi_momentum:    5-bar change in ofi_score (trend of flow)
- ofi_persistence: lag-1 autocorrelation of daily OFI (sustained vs choppy)

Output
------
- ofi_score:        composite OFI signal ∈ [-1, +1]
- tick_ofi:         normalised tick-rule flow
- liquidity_adj_ofi: normalised Amihud-adjusted flow
- vwap_deviation:   normalised VWAP deviation
- ofi_momentum:     5-day change in OFI
- ofi_persistence:  autocorrelation of OFI
- signal:           BUY / SELL / HOLD
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
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OFIResult:
    """Order Flow Imbalance result for a single symbol."""
    symbol: str

    # Composite score
    ofi_score: float = 0.0       # ∈ [-1, +1]

    # Component scores
    tick_ofi: float = 0.0
    liquidity_adj_ofi: float = 0.0
    vwap_deviation: float = 0.0

    # Flow dynamics
    ofi_momentum: float = 0.0    # 5-day change
    ofi_persistence: float = 0.0 # lag-1 autocorrelation

    # Microstructure context
    dollar_volume_m: float = 0.0   # average daily $ volume in $M
    amihud_illiq: float = 0.0      # Amihud illiquidity ratio
    spread_proxy: float = 0.0      # (high - low) / close proxy for spread

    signal: str = "HOLD"
    price: float = 0.0
    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# OFI computation
# ---------------------------------------------------------------------------

_WINDOW = 20      # rolling z-score window
_WEIGHTS = (0.45, 0.30, 0.25)   # tick, liq_adj, vwap_dev


def _zscore_series(arr: np.ndarray, window: int = 20) -> np.ndarray:
    """Rolling z-score of a 1D array."""
    s = pd.Series(arr)
    mu = s.rolling(window, min_periods=5).mean()
    sigma = s.rolling(window, min_periods=5).std() + 1e-10
    return ((s - mu) / sigma).fillna(0.0).values


def _compute_ofi_components(hist: pd.DataFrame) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Compute the three OFI components from OHLCV data.

    Returns: (tick_z, liq_adj_z, vwap_dev_z, dollar_vol, atr)
    """
    try:
        close = hist["Close"].values.astype(float)
        open_ = hist["Open"].values.astype(float)
        high = hist["High"].values.astype(float)
        low = hist["Low"].values.astype(float)
        volume = hist["Volume"].values.astype(float)

        n = len(close)
        if n < 30:
            return None

        # --- 1. Tick-rule directional flow ---
        # sign(close - open) × volume: positive = net buying
        direction = np.sign(close - open_)
        tick_flow = direction * volume

        # Rolling cumulative sum (20-day window)
        tick_cum = pd.Series(tick_flow).rolling(20, min_periods=5).sum().fillna(0.0).values
        tick_z = _zscore_series(tick_cum)
        tick_z = np.tanh(tick_z)  # bound to [-1, +1]

        # --- 2. Amihud liquidity-adjusted flow ---
        price_change = np.abs(np.diff(close, prepend=close[0]))
        amihud_illiq = price_change / (volume * close + 1e-8)  # price impact per $ volume
        # Flow = volume × direction / illiquidity (higher illiquidity → downscale flow)
        liq_adj_flow = tick_flow * (1.0 / (amihud_illiq * 1e6 + 1.0))
        liq_adj_z = _zscore_series(
            pd.Series(liq_adj_flow).rolling(20, min_periods=5).sum().fillna(0.0).values
        )
        liq_adj_z = np.tanh(liq_adj_z)

        # --- 3. VWAP deviation ---
        # VWAP ≈ (H+L+C)/3 as daily proxy
        typical_price = (high + low + close) / 3.0
        vwap_20 = pd.Series(typical_price).rolling(20, min_periods=5).mean().values

        # ATR for normalisation
        tr = np.maximum(high - low,
               np.maximum(np.abs(high - np.roll(close, 1)),
                          np.abs(low - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).ewm(span=14, min_periods=1).mean().values

        vwap_dev = (close - vwap_20) / (atr + 1e-8)
        vwap_dev_z = np.tanh(_zscore_series(vwap_dev))

        # --- Microstructure context ---
        dollar_vol = close * volume  # daily $ volume

        return tick_z, liq_adj_z, vwap_dev_z, dollar_vol, amihud_illiq

    except Exception:
        return None


# ---------------------------------------------------------------------------
# OFI Service
# ---------------------------------------------------------------------------

class OFIService:
    """Computes Order Flow Imbalance signals for individual symbols."""

    def __init__(self):
        self._cache: Dict[str, Tuple[OFIResult, datetime]] = {}
        self._cache_ttl_minutes = 10
        self._executor = ThreadPoolExecutor(max_workers=8)

    async def analyze(self, symbol: str) -> OFIResult:
        if self._is_cached(symbol):
            return self._cache[symbol][0]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._compute, symbol)
        self._cache[symbol] = (result, datetime.utcnow())
        return result

    async def analyze_universe(self, symbols: List[str]) -> List[OFIResult]:
        tasks = [self.analyze(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, OFIResult)]

    def _compute(self, symbol: str) -> OFIResult:
        result = OFIResult(symbol=symbol)
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d")
            if hist is None or len(hist) < 30:
                return result

            result.price = float(hist["Close"].iloc[-1])

            components = _compute_ofi_components(hist)
            if components is None:
                return result

            tick_z, liq_adj_z, vwap_dev_z, dollar_vol, amihud_illiq = components

            # Latest values
            tick_last = float(tick_z[-1])
            liq_last  = float(liq_adj_z[-1])
            vwap_last = float(vwap_dev_z[-1])

            # Composite
            composite = (
                _WEIGHTS[0] * tick_last +
                _WEIGHTS[1] * liq_last  +
                _WEIGHTS[2] * vwap_last
            )
            result.ofi_score = round(float(np.tanh(composite * 2)), 4)

            result.tick_ofi = round(tick_last, 4)
            result.liquidity_adj_ofi = round(liq_last, 4)
            result.vwap_deviation = round(vwap_last, 4)

            # OFI momentum: 5-day change in composite OFI
            if len(tick_z) >= 6:
                past_composite = (
                    _WEIGHTS[0] * float(tick_z[-6]) +
                    _WEIGHTS[1] * float(liq_adj_z[-6]) +
                    _WEIGHTS[2] * float(vwap_dev_z[-6])
                )
                result.ofi_momentum = round(float(composite - past_composite), 4)

            # OFI persistence: autocorrelation of daily tick OFI
            if len(tick_z) >= 10:
                series = tick_z[-20:]
                if np.std(series) > 1e-8:
                    corr = np.corrcoef(series[:-1], series[1:])[0, 1]
                    result.ofi_persistence = round(float(corr), 4)

            # Microstructure context
            result.dollar_volume_m = round(float(np.mean(dollar_vol[-20:])) / 1e6, 2)
            result.amihud_illiq = round(float(np.mean(amihud_illiq[-20:])) * 1e6, 6)
            close_arr = hist["Close"].values.astype(float)
            high_arr = hist["High"].values.astype(float)
            low_arr = hist["Low"].values.astype(float)
            result.spread_proxy = round(float(np.mean((high_arr[-20:] - low_arr[-20:]) / close_arr[-20:])) * 100, 4)

            # Signal
            if result.ofi_score > 0.2:
                result.signal = "BUY"
            elif result.ofi_score < -0.2:
                result.signal = "SELL"
            else:
                result.signal = "HOLD"

            result.data_source = "live"

        except Exception:
            result.data_source = "error"

        return result

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache:
            return False
        elapsed = (datetime.utcnow() - self._cache[symbol][1]).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ofi_service: Optional[OFIService] = None


def get_ofi_service() -> OFIService:
    global _ofi_service
    if _ofi_service is None:
        _ofi_service = OFIService()
    return _ofi_service
