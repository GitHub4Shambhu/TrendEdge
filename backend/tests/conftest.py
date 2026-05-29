"""
TrendEdge Backend - Test Fixtures & Harness

Makes the advanced trend-identification test suite **hermetic**:

* Injects a fake ``yfinance`` module into ``sys.modules`` *before* any app
  service is imported, so tests never hit the network and are fully
  deterministic.  Tests register synthetic OHLCV frames per symbol via the
  ``market`` fixture.
* Provides synthetic price-series generators (trending / choppy / high-vol /
  crashing) used across the math + service-layer tests.

Run with:  ``pytest tests/ -v``
"""

from __future__ import annotations

import sys
import types
from typing import Dict, Optional

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fake yfinance — installed into sys.modules BEFORE app services import it
# ---------------------------------------------------------------------------

# Per-symbol DataFrame registry the fake Ticker reads from.  Tests mutate this
# through the ``market`` fixture; it is reset between tests.
_MARKET_DATA: Dict[str, pd.DataFrame] = {}


class _FakeTicker:
    """Stand-in for ``yfinance.Ticker`` backed by the in-memory registry."""

    def __init__(self, symbol: str):
        self.symbol = str(symbol).upper()

    def history(self, period: str = "6mo", interval: str = "1d", **kwargs) -> pd.DataFrame:
        df = _MARKET_DATA.get(self.symbol)
        if df is None:
            return pd.DataFrame()
        return df.copy()


def _install_fake_yfinance() -> None:
    if "yfinance" in sys.modules and getattr(sys.modules["yfinance"], "_TRENDEDGE_FAKE", False):
        return
    mod = types.ModuleType("yfinance")
    mod._TRENDEDGE_FAKE = True          # type: ignore[attr-defined]
    mod.Ticker = _FakeTicker            # type: ignore[attr-defined]
    sys.modules["yfinance"] = mod


# Install immediately at import time so any `import yfinance as yf` at the top
# of an app service module resolves to the fake.
_install_fake_yfinance()


# ---------------------------------------------------------------------------
# Synthetic OHLCV generators
# ---------------------------------------------------------------------------

def make_ohlcv(
    closes: np.ndarray,
    *,
    high_low_spread: float = 0.01,
    base_volume: float = 1_000_000.0,
    volume_noise: float = 0.0,
    open_from_prev: bool = True,
    seed: int = 0,
) -> pd.DataFrame:
    """
    Build a daily OHLCV DataFrame (DatetimeIndex) from a close-price array.

    ``high``/``low`` straddle the close by ``high_low_spread`` (fractional);
    ``open`` is the previous close when ``open_from_prev`` else equal to close.
    """
    rng = np.random.default_rng(seed)
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    idx = pd.date_range(end="2024-12-31", periods=n, freq="B")

    if open_from_prev:
        opens = np.concatenate([[closes[0]], closes[:-1]])
    else:
        opens = closes.copy()

    high = np.maximum(opens, closes) * (1.0 + high_low_spread)
    low = np.minimum(opens, closes) * (1.0 - high_low_spread)

    vol = np.full(n, base_volume)
    if volume_noise > 0:
        vol = vol * (1.0 + rng.normal(0, volume_noise, n))
        vol = np.abs(vol) + 1.0

    return pd.DataFrame(
        {"Open": opens, "High": high, "Low": low, "Close": closes, "Volume": vol},
        index=idx,
    )


def trending_series(n: int = 260, start: float = 100.0, daily_drift: float = 0.004,
                    noise: float = 0.003, seed: int = 1) -> np.ndarray:
    """Geometric series with positive (or negative) drift and small noise."""
    rng = np.random.default_rng(seed)
    rets = daily_drift + rng.normal(0, noise, n)
    return start * np.exp(np.cumsum(rets))


def choppy_series(n: int = 260, start: float = 100.0, noise: float = 0.012,
                  seed: int = 2) -> np.ndarray:
    """Zero-drift random walk (no trend)."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, noise, n)
    return start * np.exp(np.cumsum(rets))


def crashing_series(n: int = 260, start: float = 100.0, seed: int = 3) -> np.ndarray:
    """Strong uptrend that reverses into a sharp drawdown in the final stretch."""
    rng = np.random.default_rng(seed)
    up = trending_series(n - 30, start=start, daily_drift=0.006, noise=0.004, seed=seed)
    peak = up[-1]
    # final 30 bars: ~ -2% per day with noise => deep drawdown
    crash_rets = -0.025 + rng.normal(0, 0.01, 30)
    crash = peak * np.exp(np.cumsum(crash_rets))
    return np.concatenate([up, crash])


def high_vol_series(n: int = 260, start: float = 100.0, seed: int = 4) -> np.ndarray:
    """Series whose volatility explodes in the recent window (regime shift)."""
    rng = np.random.default_rng(seed)
    calm = rng.normal(0, 0.004, n - 20)
    storm = rng.normal(0, 0.05, 20)
    rets = np.concatenate([calm, storm])
    return start * np.exp(np.cumsum(rets))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MarketHarness:
    """Lets a test register synthetic histories that the fake yfinance serves."""

    def set(self, symbol: str, df: pd.DataFrame) -> None:
        _MARKET_DATA[symbol.upper()] = df

    def set_closes(self, symbol: str, closes: np.ndarray, **kwargs) -> None:
        self.set(symbol, make_ohlcv(closes, **kwargs))

    def clear(self) -> None:
        _MARKET_DATA.clear()


@pytest.fixture
def market():
    """Fresh, isolated synthetic market per test."""
    harness = MarketHarness()
    harness.clear()
    yield harness
    harness.clear()


@pytest.fixture(autouse=True)
def _reset_service_singletons():
    """
    Reset module-level service singletons before each test so caches from a
    previous test never leak in.  Safe no-op if a module isn't imported.
    """
    yield
    for mod_name, attr in [
        ("app.services.kalman_trend", "_kalman_service"),
        ("app.services.hmm_regime", "_hmm_service"),
        ("app.services.transformer_trend", "_transformer_service"),
        ("app.services.sector_neutral", "_sector_neutral_service"),
        ("app.services.crash_protection", "_crash_service"),
        ("app.services.order_flow", "_ofi_service"),
        ("app.services.gnn_contagion", "_gnn_service"),
        ("app.services.unified_trend", "_unified_service"),
    ]:
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, attr):
            setattr(mod, attr, None)
