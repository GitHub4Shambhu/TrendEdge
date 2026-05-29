"""Tests for momentum crash protection."""

import numpy as np
import pytest

from app.services.crash_protection import (
    CrashProtectionService,
    VolatilityRegime,
    ExposureAction,
    get_crash_protection_service,
    _REGIME_CAPS,
)
from tests.conftest import (
    trending_series,
    choppy_series,
    crashing_series,
    high_vol_series,
)


class TestRegimeCaps:
    def test_caps_monotonic(self):
        assert (_REGIME_CAPS[VolatilityRegime.LOW]
                > _REGIME_CAPS[VolatilityRegime.NORMAL]
                > _REGIME_CAPS[VolatilityRegime.ELEVATED]
                > _REGIME_CAPS[VolatilityRegime.DANGER])


class TestCrashProtectionService:
    async def test_calm_uptrend_gives_high_exposure(self, market):
        market.set_closes("CALM", trending_series(n=200, daily_drift=0.0005, noise=0.003))
        svc = CrashProtectionService()
        r = await svc.protect("CALM")
        assert r.data_source == "live"
        assert r.exposure_scalar > 0.5
        assert r.recommended_action in (ExposureAction.FULL, ExposureAction.REDUCED)

    async def test_vol_spike_reduces_exposure(self, market):
        market.set_closes("SPIKE", high_vol_series(n=200))
        svc = CrashProtectionService()
        r = await svc.protect("SPIKE")
        # Recent vol >> 60d vol → elevated/danger regime → exposure capped down.
        assert r.vol_ratio > 1.0
        assert r.exposure_scalar < 1.0

    async def test_drawdown_flags_trend_exhaustion(self, market):
        market.set_closes("CRASH", crashing_series(n=200))
        svc = CrashProtectionService()
        r = await svc.protect("CRASH")
        assert r.drawdown_from_peak < 0          # below recent peak
        assert r.trend_exhausted is True
        assert r.exposure_scalar <= 0.3          # exhaustion cap

    async def test_exposure_bounds(self, market):
        market.set_closes("X", choppy_series(n=200, noise=0.015))
        svc = CrashProtectionService()
        r = await svc.protect("X")
        assert 0.0 <= r.exposure_scalar <= 1.5

    async def test_missing_data_defaults(self, market):
        svc = CrashProtectionService()
        r = await svc.protect("NODATA")
        assert r.exposure_scalar == 1.0          # dataclass default
        assert r.vol_regime == VolatilityRegime.NORMAL

    async def test_action_thresholds(self, market):
        market.set_closes("A", trending_series(n=200, daily_drift=0.0003, noise=0.004))
        svc = CrashProtectionService()
        r = await svc.protect("A")
        # action should be consistent with the exposure scalar bucket
        if r.exposure_scalar >= 0.9:
            assert r.recommended_action == ExposureAction.FULL
        elif r.exposure_scalar >= 0.5:
            assert r.recommended_action == ExposureAction.REDUCED
        elif r.exposure_scalar >= 0.15:
            assert r.recommended_action == ExposureAction.MINIMAL
        else:
            assert r.recommended_action == ExposureAction.CASH

    async def test_crowding_correlation(self, market):
        # Two highly-correlated names (same underlying series) → high crowding.
        base = trending_series(n=120, daily_drift=0.002)
        market.set_closes("C1", base)
        market.set_closes("C2", base * 1.01)
        svc = CrashProtectionService()
        crowding = await svc.get_crowding_risk(["C1", "C2"])
        assert 0.0 <= crowding <= 1.0
        assert crowding > 0.8

    def test_singleton(self):
        assert get_crash_protection_service() is get_crash_protection_service()
