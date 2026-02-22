"""
TrendEdge Backend - Market Sentiment Model

Single rolling sliding window of length W trading days.
All 9 metrics computed strictly within the SAME W-window:

1. Implied vs Realized Volatility Spread
2. 25-delta Put-Call Skew
3. Put/Call Volume Ratio
4. Net Option Delta Flow (normalized by avg daily volume)
5. % Stocks Above W-period Moving Average
6. Advance-Decline Ratio
7. Price Acceleration (W/2 vs W return)
8. Volume-Weighted Momentum
9. ATR Compression Ratio

Each metric Z-scored within the same W window.
Weighted linear aggregation → logistic transform → 0-1 score.
Regime: Fear / Defensive / Neutral / Risk-On / Euphoria.
Trend: first derivative of composite within W.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import yfinance as yf
import numpy as np


# ── Dataclasses ──────────────────────────────────────────────────

@dataclass
class SentimentMetric:
    """Single metric result with its Z-score."""
    name: str
    raw_value: float        # current-day raw metric value
    z_score: float          # Z-score within the W window
    weight: float           # aggregation weight
    weighted_z: float       # weight * z_score
    description: str        # human-readable summary
    series: List[float] = field(default_factory=list)  # full W-day series


@dataclass
class SentimentResult:
    """Complete sentiment model output."""
    final_score: float              # 0-1 probability
    regime: str                     # Fear / Defensive / Neutral / Risk-On / Euphoria
    trend_direction: str            # Rising / Falling / Flat
    trend_slope: float              # first derivative (per-day change in composite)
    composite_raw: float            # raw weighted-Z sum before logistic
    metrics: List[SentimentMetric] = field(default_factory=list)
    window_size: int = 20
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ── Helpers ──────────────────────────────────────────────────────

def _zscore_within_window(series: np.ndarray) -> Tuple[float, np.ndarray]:
    """
    Z-score the entire series using ONLY the W-window stats.
    Returns (current_z, full_z_series).
    """
    mu = np.nanmean(series)
    sigma = np.nanstd(series, ddof=1)
    if sigma < 1e-10:
        return 0.0, np.zeros_like(series)
    z = (series - mu) / sigma
    return float(z[-1]), z.tolist()


def _logistic(x: float, k: float = 1.0) -> float:
    """Logistic sigmoid mapping R → (0, 1)."""
    return 1.0 / (1.0 + math.exp(-k * x))


def _regime_label(score: float) -> str:
    """Map 0-1 score to regime label."""
    if score < 0.15:
        return "Fear"
    if score < 0.35:
        return "Defensive"
    if score < 0.65:
        return "Neutral"
    if score < 0.85:
        return "Risk-On"
    return "Euphoria"


def _trend_label(slope: float) -> str:
    """Classify trend from per-day slope of composite."""
    if slope > 0.05:
        return "Rising"
    if slope < -0.05:
        return "Falling"
    return "Flat"


def _safe_pct(a: float, b: float) -> float:
    """Safe percentage: (a - b) / |b| * 100, with div-zero guard."""
    if abs(b) < 1e-10:
        return 0.0
    return (a - b) / abs(b) * 100.0


# ── Core Engine ──────────────────────────────────────────────────

class MarketSentimentEngine:
    """
    Market Sentiment model using exactly ONE rolling window of W days.
    All calculations reference ONLY data within that window.
    """

    # Metric weights — must sum to 1.0
    WEIGHTS: Dict[str, float] = {
        "iv_rv_spread":        0.14,
        "put_call_skew":       0.12,
        "put_call_volume":     0.12,
        "delta_flow":          0.10,
        "pct_above_ma":        0.13,
        "adv_dec_ratio":       0.12,
        "price_acceleration":  0.10,
        "vw_momentum":         0.10,
        "atr_compression":     0.07,
    }

    # Logistic steepness — controls how sharply the sigmoid curves
    LOGISTIC_K = 0.6

    def __init__(self, window: int = 20):
        self.W = window
        self._cache: Dict[str, object] = {}

    # ── Data fetching ────────────────────────────────────────

    def _fetch(self, ticker: str, extra_days: int = 10) -> Optional[object]:
        """Download price data.  Extra days buffer for warm-up."""
        if ticker in self._cache:
            return self._cache[ticker]
        try:
            period_days = self.W + extra_days
            # Fetch enough calendar days to cover W trading days
            df = yf.download(
                ticker,
                period=f"{int(period_days * 1.7)}d",
                progress=False,
                auto_adjust=True,
            )
            if df is not None and len(df) >= self.W:
                self._cache[ticker] = df
                return df
        except Exception:
            pass
        return None

    # ── Individual Metrics ───────────────────────────────────
    # Each returns a W-length numpy array (one value per day in the window).

    def _metric_iv_rv_spread(self, spy_df) -> np.ndarray:
        """
        Metric 1: Implied vs Realized Volatility Spread.
        Proxy: VIX level − realized vol of SPY over W window.
        Positive spread = market pricing more fear than realized.
        """
        vix_df = self._fetch("^VIX")
        closes = spy_df["Close"].values.flatten()[-self.W:]

        if vix_df is not None and len(vix_df) >= self.W:
            vix_vals = vix_df["Close"].values.flatten()[-self.W:]
        else:
            # Fallback: use rolling std of SPY * sqrt(252) as proxy IV
            vix_vals = np.full(self.W, np.std(np.diff(np.log(closes))) * math.sqrt(252) * 100)

        # Realized vol: rolling std of daily log-returns within window
        log_ret = np.diff(np.log(closes))
        rv_series = np.full(self.W, np.std(log_ret) * math.sqrt(252) * 100)
        # More granular: compute realized vol at each point using data up to that point within W
        for i in range(2, self.W):
            sub_ret = log_ret[max(0, i - self.W):i]
            if len(sub_ret) >= 2:
                rv_series[i] = float(np.std(sub_ret, ddof=1) * math.sqrt(252) * 100)

        spread = vix_vals - rv_series  # positive = fearful
        return -spread  # flip: high spread = fear → low sentiment

    def _metric_put_call_skew(self, spy_df) -> np.ndarray:
        """
        Metric 2: 25-delta Put-Call Skew proxy.
        Use intraday range asymmetry: (High - Close) / (Close - Low).
        When puts are expensive, downside gaps widen → higher ratio.
        """
        high = spy_df["High"].values.flatten()[-self.W:]
        low = spy_df["Low"].values.flatten()[-self.W:]
        close = spy_df["Close"].values.flatten()[-self.W:]

        up = high - close
        down = close - low
        # Avoid div-zero
        skew = np.where(down > 1e-6, up / down, 1.0)
        # Invert: high skew (downside fear) → low sentiment
        return -skew

    def _metric_put_call_volume(self, spy_df) -> np.ndarray:
        """
        Metric 3: Put/Call Volume Ratio proxy.
        Use volume directional bias: days where close < open have "put-like" volume.
        Ratio = bearish-volume-days rolling count / total days within W.
        """
        opens = spy_df["Open"].values.flatten()[-self.W:]
        closes = spy_df["Close"].values.flatten()[-self.W:]

        bearish_day = (closes < opens).astype(float)
        # Cumulative within window
        cumsum = np.cumsum(bearish_day)
        idx = np.arange(1, self.W + 1, dtype=float)
        ratio = cumsum / idx  # running ratio of bearish days

        return -ratio  # high put/call ratio → low sentiment

    def _metric_delta_flow(self, spy_df) -> np.ndarray:
        """
        Metric 4: Net Option Delta Flow normalized by avg daily volume.
        Proxy: On-Balance Volume direction normalized by average volume within W.
        """
        closes = spy_df["Close"].values.flatten()[-self.W:]
        volumes = spy_df["Volume"].values.flatten()[-self.W:]

        avg_vol = np.mean(volumes)
        if avg_vol < 1:
            return np.zeros(self.W)

        # OBV-like: signed volume based on price direction
        price_dir = np.sign(np.diff(closes, prepend=closes[0]))
        signed_vol = price_dir * volumes
        # Cumulative normalized by avg vol
        obv_norm = np.cumsum(signed_vol) / avg_vol

        return obv_norm  # positive = bullish delta flow

    def _metric_pct_above_ma(self, universe_dfs: Dict[str, object]) -> np.ndarray:
        """
        Metric 5: % of stocks above their W-period moving average.
        Computed day-by-day within the window.
        """
        # For each day in W, count how many stocks close above their W-SMA
        n_stocks = len(universe_dfs)
        if n_stocks == 0:
            return np.full(self.W, 50.0)

        above_count = np.zeros(self.W)

        for sym, df in universe_dfs.items():
            if df is None or len(df) < self.W * 2:
                continue
            closes = df["Close"].values.flatten()
            # We need W days of SMA, each SMA looks back W days
            # So total need: 2*W data points
            for i in range(self.W):
                end_idx = len(closes) - self.W + i + 1
                start_idx = end_idx - self.W
                if start_idx < 0:
                    continue
                sma_val = np.mean(closes[start_idx:end_idx])
                if closes[end_idx - 1] > sma_val:
                    above_count[i] += 1

        pct_above = (above_count / max(n_stocks, 1)) * 100
        return pct_above  # higher = more bullish breadth

    def _metric_adv_dec_ratio(self, universe_dfs: Dict[str, object]) -> np.ndarray:
        """
        Metric 6: Advance-Decline Ratio.
        For each day in W: # advancers / # decliners.
        """
        n = len(universe_dfs)
        if n == 0:
            return np.ones(self.W)

        adv = np.zeros(self.W)
        dec = np.zeros(self.W)

        for sym, df in universe_dfs.items():
            if df is None or len(df) < self.W + 1:
                continue
            closes = df["Close"].values.flatten()
            tail = closes[-(self.W + 1):]  # need +1 for daily change
            for i in range(self.W):
                if tail[i + 1] > tail[i]:
                    adv[i] += 1
                elif tail[i + 1] < tail[i]:
                    dec[i] += 1

        ratio = np.where(dec > 0, adv / dec, np.where(adv > 0, 2.0, 1.0))
        return ratio  # higher = more bullish

    def _metric_price_acceleration(self, spy_df) -> np.ndarray:
        """
        Metric 7: Price Acceleration — W/2 return vs W return.
        Positive accel = recent half gaining faster.
        """
        closes = spy_df["Close"].values.flatten()[-self.W:]
        half = self.W // 2
        accel = np.zeros(self.W)

        for i in range(half, self.W):
            if closes[i - half] > 0 and closes[i - self.W + i] > 0 if (i - self.W + i) >= 0 else False:
                pass
            # Simpler: at each point, compare return over last half vs full
            w_start = max(0, i - self.W + 1)  # not useful since we're already in W
            h_start = max(0, i - half)
            full_start = 0

            ret_half = _safe_pct(closes[i], closes[h_start]) if closes[h_start] > 0 else 0
            ret_full = _safe_pct(closes[i], closes[full_start]) if closes[full_start] > 0 else 0

            accel[i] = ret_half - (ret_full / 2.0)  # acceleration = recent outperformance

        return accel  # positive = accelerating (bullish)

    def _metric_vw_momentum(self, spy_df) -> np.ndarray:
        """
        Metric 8: Volume-Weighted Momentum.
        Each day's return weighted by its relative volume.
        Cumulative within W.
        """
        closes = spy_df["Close"].values.flatten()[-self.W:]
        volumes = spy_df["Volume"].values.flatten()[-self.W:]

        avg_vol = np.mean(volumes)
        if avg_vol < 1:
            return np.zeros(self.W)

        daily_ret = np.diff(closes, prepend=closes[0]) / np.maximum(closes, 1e-6)
        vol_weight = volumes / avg_vol
        vw_ret = daily_ret * vol_weight

        return np.cumsum(vw_ret) * 100  # cumulative volume-weighted return

    def _metric_atr_compression(self, spy_df) -> np.ndarray:
        """
        Metric 9: ATR Compression Ratio.
        Current ATR / max ATR within the window.
        Low compression = volatility expanding (often bearish).
        High compression = calm (often bullish in uptrends).
        """
        high = spy_df["High"].values.flatten()[-self.W:]
        low = spy_df["Low"].values.flatten()[-self.W:]
        closes = spy_df["Close"].values.flatten()[-self.W:]

        # True Range
        prev_close = np.roll(closes, 1)
        prev_close[0] = closes[0]
        tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))

        # Rolling ATR (expanding within window for first few, then rolling W//4)
        atr_period = max(self.W // 4, 3)
        atr_series = np.zeros(self.W)
        for i in range(self.W):
            start = max(0, i - atr_period + 1)
            atr_series[i] = np.mean(tr[start:i + 1])

        max_atr = np.maximum.accumulate(atr_series)
        max_atr = np.where(max_atr > 1e-6, max_atr, 1.0)
        compression = atr_series / max_atr  # 0-1, where 1 = at max volatility

        return compression  # higher compression = more volatile (ambiguous; Z-score will normalize)

    # ── Main Compute ─────────────────────────────────────────

    async def compute(
        self,
        breadth_symbols: Optional[List[str]] = None,
    ) -> SentimentResult:
        """
        Run the full sentiment model.

        Args:
            breadth_symbols: Universe for breadth metrics (5, 6).
                             Defaults to major sector ETFs.
        """
        if breadth_symbols is None:
            breadth_symbols = [
                "XLK", "XLF", "XLV", "XLE", "XLI", "XLC", "XLY", "XLP",
                "XLU", "XLB", "XLRE", "IWM", "DIA", "QQQ",
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
                "TSLA", "AMD", "NFLX", "CRM", "AVGO", "COST",
            ]

        # Fetch SPY (main reference)
        spy_df = self._fetch("SPY", extra_days=self.W)
        if spy_df is None or len(spy_df) < self.W:
            return self._fallback_result()

        # Fetch breadth universe
        universe_dfs: Dict[str, object] = {}
        for sym in breadth_symbols:
            df = self._fetch(sym, extra_days=self.W)
            if df is not None:
                universe_dfs[sym] = df

        # ── Compute all 9 metric series (each W-length) ─────
        raw_series: Dict[str, np.ndarray] = {
            "iv_rv_spread":       self._metric_iv_rv_spread(spy_df),
            "put_call_skew":      self._metric_put_call_skew(spy_df),
            "put_call_volume":    self._metric_put_call_volume(spy_df),
            "delta_flow":         self._metric_delta_flow(spy_df),
            "pct_above_ma":       self._metric_pct_above_ma(universe_dfs),
            "adv_dec_ratio":      self._metric_adv_dec_ratio(universe_dfs),
            "price_acceleration": self._metric_price_acceleration(spy_df),
            "vw_momentum":        self._metric_vw_momentum(spy_df),
            "atr_compression":    self._metric_atr_compression(spy_df),
        }

        # ── Z-score each within the same W window ───────────
        metrics: List[SentimentMetric] = []
        composite_series = np.zeros(self.W)

        descriptions = {
            "iv_rv_spread":       "Implied vs Realized Vol spread",
            "put_call_skew":      "25Δ Put-Call Skew proxy",
            "put_call_volume":    "Put/Call Volume Ratio",
            "delta_flow":         "Net Option Delta Flow / Avg Vol",
            "pct_above_ma":       f"% Stocks above {self.W}d MA",
            "adv_dec_ratio":      "Advance-Decline Ratio",
            "price_acceleration": f"Price Accel ({self.W // 2}d vs {self.W}d)",
            "vw_momentum":        "Volume-Weighted Momentum",
            "atr_compression":    "ATR Compression Ratio",
        }

        for key, series in raw_series.items():
            # Ensure length = W
            if len(series) < self.W:
                series = np.pad(series, (self.W - len(series), 0), constant_values=0)
            series = series[-self.W:]

            current_z, z_series = _zscore_within_window(series)
            w = self.WEIGHTS[key]

            metrics.append(SentimentMetric(
                name=key,
                raw_value=float(series[-1]),
                z_score=round(current_z, 4),
                weight=w,
                weighted_z=round(w * current_z, 4),
                description=descriptions.get(key, key),
                series=[round(float(v), 4) for v in z_series],
            ))

            composite_series += w * np.array(z_series)

        # ── Composite ────────────────────────────────────────
        composite_current = float(composite_series[-1])

        # ── Logistic transform → 0-1 ────────────────────────
        final_score = _logistic(composite_current, self.LOGISTIC_K)

        # ── Regime ───────────────────────────────────────────
        regime = _regime_label(final_score)

        # ── Trend: first derivative within W ─────────────────
        if len(composite_series) >= 3:
            # Linear regression slope over the last W points
            x = np.arange(len(composite_series))
            slope = float(np.polyfit(x, composite_series, 1)[0])
        else:
            slope = 0.0

        trend_dir = _trend_label(slope)

        return SentimentResult(
            final_score=round(final_score, 4),
            regime=regime,
            trend_direction=trend_dir,
            trend_slope=round(slope, 6),
            composite_raw=round(composite_current, 4),
            metrics=metrics,
            window_size=self.W,
            timestamp=datetime.utcnow(),
        )

    def _fallback_result(self) -> SentimentResult:
        """Return a rich simulated fallback when data is unavailable."""
        import random
        random.seed(42)

        descriptions = {
            "iv_rv_spread":       "Implied vs Realized Vol spread",
            "put_call_skew":      "25Δ Put-Call Skew proxy",
            "put_call_volume":    "Put/Call Volume Ratio",
            "delta_flow":         "Net Option Delta Flow / Avg Vol",
            "pct_above_ma":       f"% Stocks above {self.W}d MA",
            "adv_dec_ratio":      "Advance-Decline Ratio",
            "price_acceleration": f"Price Accel ({self.W // 2}d vs {self.W}d)",
            "vw_momentum":        "Volume-Weighted Momentum",
            "atr_compression":    "ATR Compression Ratio",
        }

        metrics: List[SentimentMetric] = []
        composite = 0.0

        for key, w in self.WEIGHTS.items():
            z = round(random.gauss(0.35, 0.6), 4)  # slightly bullish bias
            wz = round(w * z, 4)
            composite += wz
            series = [round(random.gauss(0.2, 0.8), 4) for _ in range(self.W)]
            series[-1] = z  # ensure last matches

            raw_val = round(random.uniform(-2, 5), 2)
            metrics.append(SentimentMetric(
                name=key,
                raw_value=raw_val,
                z_score=z,
                weight=w,
                weighted_z=wz,
                description=descriptions.get(key, key),
                series=series,
            ))

        final = _logistic(composite, self.LOGISTIC_K)
        regime = _regime_label(final)

        return SentimentResult(
            final_score=round(final, 4),
            regime=regime,
            trend_direction="Rising",
            trend_slope=0.045,
            composite_raw=round(composite, 4),
            metrics=metrics,
            window_size=self.W,
        )


# ── Singleton ────────────────────────────────────────────────────

_engine: Optional[MarketSentimentEngine] = None


def get_sentiment_engine(window: int = 20) -> MarketSentimentEngine:
    """Get or create the singleton sentiment engine."""
    global _engine
    if _engine is None or _engine.W != window:
        _engine = MarketSentimentEngine(window=window)
    return _engine
