"""Tests for the Order Flow Imbalance (OFI) signal."""

import numpy as np
import pytest

from app.services.order_flow import (
    OFIService,
    _zscore_series,
    _compute_ofi_components,
    _WEIGHTS,
    get_ofi_service,
)
from tests.conftest import make_ohlcv, trending_series, choppy_series


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestZScoreHelper:
    def test_zscore_centres_and_scales(self):
        arr = np.arange(100, dtype=float)
        z = _zscore_series(arr, window=20)
        assert len(z) == 100
        assert np.isfinite(z).all()

    def test_constant_series_zero(self):
        z = _zscore_series(np.full(50, 7.0), window=20)
        # constant input → zero numerator → all zeros
        np.testing.assert_allclose(z, 0.0, atol=1e-6)


class TestWeights:
    def test_weights_sum_to_one(self):
        assert sum(_WEIGHTS) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Component computation
# ---------------------------------------------------------------------------

class TestOFIComponents:
    def test_returns_five_arrays(self):
        df = make_ohlcv(trending_series(n=100))
        out = _compute_ofi_components(df)
        assert out is not None
        assert len(out) == 5
        tick_z, liq_z, vwap_z, dollar_vol, amihud = out
        assert len(tick_z) == 100
        assert np.abs(tick_z).max() <= 1.0          # tanh-bounded
        assert np.abs(vwap_z).max() <= 1.0

    def test_short_history_none(self):
        df = make_ohlcv(trending_series(n=20))
        assert _compute_ofi_components(df) is None


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

def _accelerating_volume(closes, *, ramp_last=15, surge=4.0, seed=0):
    """OHLCV where volume surges in the final `ramp_last` bars (flow acceleration)."""
    df = make_ohlcv(closes, base_volume=1_000_000.0, volume_noise=0.05, seed=seed)
    df.iloc[-ramp_last:, df.columns.get_loc("Volume")] *= surge
    return df


class TestOFIService:
    async def test_accelerating_buy_beats_accelerating_sell(self, market):
        # OFI components are flow *deviations* (z-scored), so the directional test
        # is a recent surge: rising closes + late volume surge should score higher
        # than the mirror-image falling series.
        up = trending_series(n=120, daily_drift=0.006, noise=0.001)
        down = trending_series(n=120, daily_drift=-0.006, noise=0.001, seed=8)
        market.set("BUY", _accelerating_volume(up, seed=1))
        market.set("SELL", _accelerating_volume(down, seed=2))
        svc = OFIService()
        rb = await svc.analyze("BUY")
        rs = await svc.analyze("SELL")
        assert rb.data_source == "live" and rs.data_source == "live"
        assert -1.0 <= rb.ofi_score <= 1.0
        assert rb.ofi_score > rs.ofi_score

    async def test_score_bounded_and_components_present(self, market):
        market.set_closes("X", choppy_series(n=120, noise=0.02))
        svc = OFIService()
        r = await svc.analyze("X")
        assert -1.0 <= r.ofi_score <= 1.0
        assert -1.0 <= r.tick_ofi <= 1.0
        assert -1.0 <= r.vwap_deviation <= 1.0
        assert r.dollar_volume_m >= 0

    async def test_persistence_in_range(self, market):
        market.set_closes("P", trending_series(n=120, daily_drift=0.003))
        svc = OFIService()
        r = await svc.analyze("P")
        assert -1.0 <= r.ofi_persistence <= 1.0

    async def test_missing_data(self, market):
        svc = OFIService()
        r = await svc.analyze("NODATA")
        assert r.ofi_score == 0.0
        assert r.signal == "HOLD"

    async def test_signal_consistency(self, market):
        market.set_closes("S", trending_series(n=120, daily_drift=0.006, noise=0.001))
        svc = OFIService()
        r = await svc.analyze("S")
        if r.ofi_score > 0.2:
            assert r.signal == "BUY"
        elif r.ofi_score < -0.2:
            assert r.signal == "SELL"
        else:
            assert r.signal == "HOLD"

    def test_singleton(self):
        assert get_ofi_service() is get_ofi_service()
