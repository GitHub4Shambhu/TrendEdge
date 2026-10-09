"""
TrendEdge Backend - Performance Comparison Service

Real multi-timeframe performance (1W → 5Y, YTD), volatility and volume stats
for a set of tickers, from one batched yfinance download. Used to compare the
momentum scan's picks ("captured") against the universe's biggest recent
movers that the scan did not pick ("missed").
"""

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import pandas as pd
import yfinance as yf

# Trading-day lookbacks per column
HORIZONS = {"week": 5, "month": 21, "quarter": 63, "half": 126, "year": 252, "y3": 756, "y5": 1260}


@dataclass
class PerformanceRow:
    symbol: str
    price: float
    change: float                      # 1-day %
    perf_week: Optional[float]
    perf_month: Optional[float]
    perf_quarter: Optional[float]
    perf_half: Optional[float]
    perf_ytd: Optional[float]
    perf_year: Optional[float]
    perf_3y: Optional[float]
    perf_5y: Optional[float]
    volatility_week: float             # avg daily high-low range %, last 5 days
    volatility_month: float            # same, last 21 days
    avg_volume: float                  # 63-day average shares
    rel_volume: float                  # last day / avg_volume
    volume: float                      # last day shares


def _pct(close: pd.Series, days: int) -> Optional[float]:
    """% return over the last `days` trading days, or None if history is too short."""
    if len(close) <= days:
        return None
    return float((close.iloc[-1] / close.iloc[-1 - days] - 1) * 100)


def _compute_row(symbol: str, df: pd.DataFrame) -> Optional[PerformanceRow]:
    df = df.dropna(subset=["Close"])
    if len(df) < 2:
        return None
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    prior_year = close[close.index.year < close.index[-1].year]
    ytd = float((close.iloc[-1] / prior_year.iloc[-1] - 1) * 100) if len(prior_year) else None

    daily_range = (high - low) / close * 100
    avg_vol = float(vol.iloc[-63:].mean())

    return PerformanceRow(
        symbol=symbol,
        price=float(close.iloc[-1]),
        change=float((close.iloc[-1] / close.iloc[-2] - 1) * 100),
        perf_week=_pct(close, HORIZONS["week"]),
        perf_month=_pct(close, HORIZONS["month"]),
        perf_quarter=_pct(close, HORIZONS["quarter"]),
        perf_half=_pct(close, HORIZONS["half"]),
        perf_ytd=ytd,
        perf_year=_pct(close, HORIZONS["year"]),
        perf_3y=_pct(close, HORIZONS["y3"]),
        perf_5y=_pct(close, HORIZONS["y5"]),
        volatility_week=float(daily_range.iloc[-5:].mean()),
        volatility_month=float(daily_range.iloc[-21:].mean()),
        avg_volume=avg_vol,
        rel_volume=float(vol.iloc[-1] / avg_vol) if avg_vol > 0 else 1.0,
        volume=float(vol.iloc[-1]),
    )


class PerformanceComparisonService:
    """Computes PerformanceRows with a per-symbol 30-minute cache."""

    CACHE_TTL = 30 * 60

    def __init__(self) -> None:
        self._cache: Dict[str, tuple] = {}  # symbol -> (timestamp, Optional[PerformanceRow])

    def _download(self, symbols: List[str]) -> Dict[str, Optional[PerformanceRow]]:
        data = yf.download(
            symbols, period="10y", group_by="ticker",
            auto_adjust=True, threads=True, progress=False,
        )
        rows: Dict[str, Optional[PerformanceRow]] = {}
        for sym in symbols:
            try:
                frame = data[sym] if isinstance(data.columns, pd.MultiIndex) else data
                rows[sym] = _compute_row(sym, frame)
            except (KeyError, IndexError, ValueError):
                rows[sym] = None
        return rows

    async def get_rows(self, symbols: Iterable[str]) -> Dict[str, PerformanceRow]:
        """Rows for every symbol Yahoo has data for; symbols without data are omitted."""
        now = time.time()
        wanted = list(dict.fromkeys(symbols))
        stale = [s for s in wanted if s not in self._cache or now - self._cache[s][0] > self.CACHE_TTL]
        if stale:
            loop = asyncio.get_event_loop()
            fresh = await loop.run_in_executor(None, self._download, stale)
            for sym in stale:
                self._cache[sym] = (now, fresh.get(sym))
        result = {}
        for sym in wanted:
            row = self._cache[sym][1]
            if row is not None and not math.isnan(row.price):
                result[sym] = row
        return result


_service: Optional[PerformanceComparisonService] = None


def get_performance_service() -> PerformanceComparisonService:
    global _service
    if _service is None:
        _service = PerformanceComparisonService()
    return _service
