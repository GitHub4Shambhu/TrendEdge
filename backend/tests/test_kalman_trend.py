"""Tests for the Kalman Filter adaptive trend estimator."""

import numpy as np
import pytest

from app.services.kalman_trend import (
    KalmanPriceFilter,
    KalmanTrendService,
    get_kalman_service,
)
from tests.conftest import trending_series, choppy_series


# ---------------------------------------------------------------------------
# Core filter math
# ---------------------------------------------------------------------------

class TestKalmanPriceFilter:
    def test_tracks_constant_price(self):
        """On a flat price the level converges to it and velocity → ~0."""
        kf = KalmanPriceFilter()
        prices = np.full(100, 50.0)
        levels, velocities = kf.filter_series(prices)
        assert levels[-1] == pytest.approx(50.0, abs=1e-3)
        assert abs(velocities[-1]) < 1e-2

    def test_velocity_matches_linear_ramp_slope(self):
        """On a constant-slope ramp the estimated velocity ≈ the true slope."""
        slope = 0.5
        prices = 100.0 + slope * np.arange(200)
        kf = KalmanPriceFilter(
            process_noise_level=1e-2,
            process_noise_velocity=1e-3,
            measurement_noise=1e-2,
        )
        _, velocities = kf.filter_series(prices)
        # allow convergence transient — check the tail
        assert np.mean(velocities[-20:]) == pytest.approx(slope, abs=0.1)

    def test_velocity_sign_follows_direction(self):
        kf_up = KalmanPriceFilter()
        _, vel_up = kf_up.filter_series(trending_series(daily_drift=0.01))
        assert vel_up[-1] > 0

        kf_down = KalmanPriceFilter()
        _, vel_down = kf_down.filter_series(trending_series(daily_drift=-0.01, seed=9))
        assert vel_down[-1] < 0

    def test_first_observation_initialises_state(self):
        kf = KalmanPriceFilter()
        level, vel = kf.update(123.45)
        assert level == 123.45
        assert vel == 0.0

    def test_smoother_than_raw_prices(self):
        """The Kalman level should have lower variance of first-difference than noisy input."""
        prices = choppy_series(noise=0.02)
        kf = KalmanPriceFilter()
        levels, _ = kf.filter_series(prices)
        raw_diff_var = np.var(np.diff(prices))
        smooth_diff_var = np.var(np.diff(levels))
        assert smooth_diff_var < raw_diff_var


# ---------------------------------------------------------------------------
# Service layer (uses fake yfinance via the `market` fixture)
# ---------------------------------------------------------------------------

class TestKalmanService:
    async def test_uptrend_yields_buy_or_up(self, market):
        market.set_closes("UP", trending_series(daily_drift=0.012, noise=0.002))
        svc = KalmanTrendService()
        r = await svc.analyze("UP")
        assert r.data_source == "live"
        assert r.trend_direction == "UP"
        assert r.kalman_signal > 0

    async def test_downtrend_yields_down(self, market):
        market.set_closes("DN", trending_series(daily_drift=-0.012, noise=0.002, seed=7))
        svc = KalmanTrendService()
        r = await svc.analyze("DN")
        assert r.trend_direction == "DOWN"
        # kalman_signal is a velocity *z-score* (acceleration), not the trend sign;
        # the latent velocity itself is the directional measure.
        assert r.kalman_velocity < 0

    async def test_missing_data_is_handled_gracefully(self, market):
        # no data registered for this symbol
        svc = KalmanTrendService()
        r = await svc.analyze("NODATA")
        assert r.symbol == "NODATA"
        assert r.signal == "HOLD"
        assert r.kalman_signal == 0.0

    async def test_signal_bounded(self, market):
        market.set_closes("VOL", choppy_series(noise=0.03))
        svc = KalmanTrendService()
        r = await svc.analyze("VOL")
        assert -1.0 <= r.kalman_signal <= 1.0
        assert -1.0 <= r.composite_signal <= 1.0

    async def test_cache_hit_returns_same_object(self, market):
        market.set_closes("CACHE", trending_series())
        svc = KalmanTrendService()
        first = await svc.analyze("CACHE")
        second = await svc.analyze("CACHE")
        assert first is second  # served from cache

    async def test_universe_analysis(self, market):
        market.set_closes("A", trending_series(daily_drift=0.01))
        market.set_closes("B", trending_series(daily_drift=-0.01, seed=5))
        svc = KalmanTrendService()
        results = await svc.analyze_universe(["A", "B"])
        assert len(results) == 2
        by_sym = {r.symbol: r for r in results}
        assert by_sym["A"].kalman_velocity > 0
        assert by_sym["B"].kalman_velocity < 0

    def test_singleton(self):
        assert get_kalman_service() is get_kalman_service()
