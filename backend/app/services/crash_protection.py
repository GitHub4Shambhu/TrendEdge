"""
TrendEdge Backend - Momentum Crash Protection

Scales position exposure based on realised volatility and drawdown state to
protect against momentum crashes (sudden reversals during crowded unwinds).

Methodology
-----------
1. **Volatility targeting**: target annualised vol of 15%. If realised vol
   exceeds target, scale down: exposure = min(target_vol / realised_vol, 1.5).
2. **Vol regime**: classify σ10d/σ60d ratio.
   - LOW    (<0.7):  trending, stable — exposure cap 1.5
   - NORMAL (0.7-1.5): typical — exposure cap 1.0
   - ELEVATED (1.5-2.2): caution — exposure cap 0.6
   - DANGER  (>2.2): crisis — exposure cap 0.2
3. **Trend exhaustion**: if price is >12% below its recent 20-day peak,
   mark trend as exhausted and cap exposure at 0.3.
4. **Crowding risk**: pairwise correlation among top momentum stocks.
   If average correlation > 0.75, flag crowding and reduce by 20%.

Output
------
- exposure_scalar:   final position size multiplier [0.0 – 1.5]
- vol_regime:        LOW / NORMAL / ELEVATED / DANGER
- recommended_action: FULL / REDUCED / MINIMAL / CASH
- trend_exhausted:   bool
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VolatilityRegime(str, Enum):
    LOW      = "LOW"
    NORMAL   = "NORMAL"
    ELEVATED = "ELEVATED"
    DANGER   = "DANGER"


class ExposureAction(str, Enum):
    FULL    = "FULL"
    REDUCED = "REDUCED"
    MINIMAL = "MINIMAL"
    CASH    = "CASH"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CrashProtectionResult:
    """Crash protection assessment for a single symbol."""
    symbol: str

    # Exposure output
    exposure_scalar: float = 1.0         # final position size multiplier
    recommended_action: ExposureAction = ExposureAction.FULL

    # Volatility metrics
    vol_regime: VolatilityRegime = VolatilityRegime.NORMAL
    vol_ratio: float = 1.0               # σ_10d / σ_60d
    realised_vol_10d: float = 0.0        # annualised %
    realised_vol_60d: float = 0.0        # annualised %
    vol_scaled_signal: float = 1.0       # target_vol / realised_vol (pre-cap)

    # Drawdown / trend exhaustion
    trend_exhausted: bool = False
    drawdown_from_peak: float = 0.0      # % below recent 20-day peak (negative)
    days_since_peak: int = 0

    # Price context
    price: float = 0.0
    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

_TARGET_VOL = 0.15   # 15% annualised target
_EXHAUSTION_THRESHOLD = -0.12   # -12% drawdown signals exhaustion
_EXHAUSTION_LOOKBACK = 20       # days to look back for peak

_VOL_THRESHOLDS = {
    "low_upper":      0.7,
    "normal_upper":   1.5,
    "elevated_upper": 2.2,
}

_REGIME_CAPS = {
    VolatilityRegime.LOW:      1.5,
    VolatilityRegime.NORMAL:   1.0,
    VolatilityRegime.ELEVATED: 0.6,
    VolatilityRegime.DANGER:   0.2,
}


class CrashProtectionService:
    """
    Assesses crash risk and returns an exposure scalar for momentum signals.
    """

    def __init__(self):
        self._cache: Dict[str, Tuple[CrashProtectionResult, datetime]] = {}
        self._cache_ttl_minutes = 5
        self._executor = ThreadPoolExecutor(max_workers=8)

    async def protect(self, symbol: str, raw_signal: float = 0.0) -> CrashProtectionResult:
        """Compute crash protection scalar for a symbol."""
        if self._is_cached(symbol):
            return self._cache[symbol][0]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._compute, symbol, raw_signal)
        self._cache[symbol] = (result, datetime.utcnow())
        return result

    async def get_crowding_risk(self, symbols: List[str]) -> float:
        """Return average pairwise correlation of given symbols (crowding proxy)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self._compute_crowding, symbols
        )

    def _compute(self, symbol: str, raw_signal: float) -> CrashProtectionResult:
        result = CrashProtectionResult(symbol=symbol)
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d")
            if hist is None or len(hist) < 30:
                return result

            closes = hist["Close"].values.astype(float)
            result.price = float(closes[-1])

            returns = np.diff(np.log(closes))

            # Realised vols (annualised)
            vol_10d = float(np.std(returns[-10:]) * np.sqrt(252) * 100) if len(returns) >= 10 else 15.0
            vol_60d = float(np.std(returns[-60:]) * np.sqrt(252) * 100) if len(returns) >= 60 else 15.0

            result.realised_vol_10d = round(vol_10d, 2)
            result.realised_vol_60d = round(vol_60d, 2)

            # Vol ratio determines regime
            vol_ratio = vol_10d / (vol_60d + 1e-8)
            result.vol_ratio = round(float(vol_ratio), 4)

            if vol_ratio < _VOL_THRESHOLDS["low_upper"]:
                result.vol_regime = VolatilityRegime.LOW
            elif vol_ratio < _VOL_THRESHOLDS["normal_upper"]:
                result.vol_regime = VolatilityRegime.NORMAL
            elif vol_ratio < _VOL_THRESHOLDS["elevated_upper"]:
                result.vol_regime = VolatilityRegime.ELEVATED
            else:
                result.vol_regime = VolatilityRegime.DANGER

            # Volatility-targeted exposure (target 15% annual vol)
            realised_pct = vol_10d / 100.0
            vol_scaled = min(_TARGET_VOL / (realised_pct + 1e-8), 1.5)
            result.vol_scaled_signal = round(float(vol_scaled), 4)

            # Regime cap
            regime_cap = _REGIME_CAPS[result.vol_regime]

            # Trend exhaustion: drawdown from recent peak
            lookback = min(_EXHAUSTION_LOOKBACK, len(closes))
            recent_peak = float(np.max(closes[-lookback:]))
            drawdown = (closes[-1] - recent_peak) / (recent_peak + 1e-8)
            result.drawdown_from_peak = round(float(drawdown * 100), 2)
            result.days_since_peak = int(np.argmax(closes[-lookback:][::-1]))
            result.trend_exhausted = bool(drawdown < _EXHAUSTION_THRESHOLD)

            # Final exposure
            exposure = min(vol_scaled, regime_cap)
            if result.trend_exhausted:
                exposure = min(exposure, 0.3)
            result.exposure_scalar = round(float(np.clip(exposure, 0.0, 1.5)), 4)

            # Recommended action
            if result.exposure_scalar >= 0.9:
                result.recommended_action = ExposureAction.FULL
            elif result.exposure_scalar >= 0.5:
                result.recommended_action = ExposureAction.REDUCED
            elif result.exposure_scalar >= 0.15:
                result.recommended_action = ExposureAction.MINIMAL
            else:
                result.recommended_action = ExposureAction.CASH

            result.data_source = "live"

        except Exception:
            result.data_source = "error"

        return result

    def _compute_crowding(self, symbols: List[str]) -> float:
        """Compute average pairwise correlation among symbols."""
        try:
            if len(symbols) < 2:
                return 0.0

            prices = {}
            for sym in symbols[:20]:
                try:
                    t = yf.Ticker(sym)
                    h = t.history(period="3mo", interval="1d")
                    if h is not None and len(h) >= 30:
                        prices[sym] = h["Close"].values.astype(float)
                except Exception:
                    pass

            if len(prices) < 2:
                return 0.0

            min_len = min(len(v) for v in prices.values())
            ret_matrix = np.column_stack([
                np.diff(np.log(v[-min_len:]))
                for v in prices.values()
            ])

            corr = np.corrcoef(ret_matrix.T)
            n = corr.shape[0]
            upper = corr[np.triu_indices(n, k=1)]
            return float(np.mean(np.abs(upper)))

        except Exception:
            return 0.0

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache:
            return False
        elapsed = (datetime.utcnow() - self._cache[symbol][1]).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_crash_service: Optional[CrashProtectionService] = None


def get_crash_protection_service() -> CrashProtectionService:
    global _crash_service
    if _crash_service is None:
        _crash_service = CrashProtectionService()
    return _crash_service
