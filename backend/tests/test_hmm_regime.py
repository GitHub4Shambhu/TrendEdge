"""Tests for the HMM market-regime detector."""

import numpy as np
import pytest

from app.services.hmm_regime import (
    GaussianHMM,
    HMMRegime,
    HMMRegimeService,
    get_hmm_regime_service,
    _REGIME_MULTIPLIERS,
)
from tests.conftest import trending_series, choppy_series


# ---------------------------------------------------------------------------
# Core Gaussian HMM math
# ---------------------------------------------------------------------------

class TestGaussianHMM:
    def _two_regime_obs(self, seed=0):
        """200 samples: first half centred at -3, second half at +3 (1-D, padded to 2-D)."""
        rng = np.random.default_rng(seed)
        a = rng.normal(-3.0, 0.4, (100, 2))
        b = rng.normal(+3.0, 0.4, (100, 2))
        return np.vstack([a, b])

    def test_fit_sets_parameters(self):
        obs = self._two_regime_obs()
        hmm = GaussianHMM(n_states=3, n_iter=30).fit(obs)
        assert hmm.means_.shape == (3, 2)
        assert hmm.transmat_.shape == (3, 3)
        # rows of transition matrix are probability distributions
        np.testing.assert_allclose(hmm.transmat_.sum(axis=1), 1.0, atol=1e-6)
        np.testing.assert_allclose(hmm.startprob_.sum(), 1.0, atol=1e-6)

    def test_separates_two_distinct_clusters(self):
        obs = self._two_regime_obs()
        hmm = GaussianHMM(n_states=3, n_iter=50).fit(obs)
        states = hmm.predict(obs)
        # The first 100 and last 100 samples should be dominated by different states.
        first_mode = np.bincount(states[:100]).argmax()
        last_mode = np.bincount(states[100:]).argmax()
        assert first_mode != last_mode

    def test_predict_proba_normalised(self):
        obs = self._two_regime_obs()
        hmm = GaussianHMM(n_states=3, n_iter=20).fit(obs)
        proba = hmm.predict_proba(obs)
        assert proba.shape == (200, 3)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-5)
        assert (proba >= 0).all()

    def test_viterbi_length(self):
        obs = self._two_regime_obs()
        hmm = GaussianHMM(n_states=3, n_iter=10).fit(obs)
        states = hmm.predict(obs)
        assert states.shape == (200,)
        assert states.min() >= 0 and states.max() < 3


# ---------------------------------------------------------------------------
# Regime multipliers
# ---------------------------------------------------------------------------

class TestRegimeMultipliers:
    def test_ordering(self):
        assert _REGIME_MULTIPLIERS[HMMRegime.RISK_ON] == 1.0
        assert _REGIME_MULTIPLIERS[HMMRegime.NEUTRAL] == 0.7
        assert _REGIME_MULTIPLIERS[HMMRegime.RISK_OFF] == 0.3
        # monotonic: risk-on >= neutral >= risk-off
        assert (_REGIME_MULTIPLIERS[HMMRegime.RISK_ON]
                >= _REGIME_MULTIPLIERS[HMMRegime.NEUTRAL]
                >= _REGIME_MULTIPLIERS[HMMRegime.RISK_OFF])


# ---------------------------------------------------------------------------
# Service layer (SPY feed mocked through fake yfinance)
# ---------------------------------------------------------------------------

def _ends_in_rally(n=500, seed=11):
    calm = choppy_series(n=n - 20, noise=0.006, seed=seed)
    rally = calm[-1] * np.exp(np.cumsum(np.full(20, 0.02)))
    return np.concatenate([calm, rally])


def _ends_in_crash(n=500, seed=12):
    calm = choppy_series(n=n - 20, noise=0.006, seed=seed)
    crash = calm[-1] * np.exp(np.cumsum(np.full(20, -0.025)))
    return np.concatenate([calm, crash])


class TestHMMRegimeService:
    async def test_recent_rally_is_risk_on(self, market):
        # The regime reflects *recent* return dynamics (windowed detector):
        # a sharp final rally should classify RISK_ON and never RISK_OFF.
        market.set_closes("SPY", _ends_in_rally())
        svc = HMMRegimeService()
        r = await svc.get_regime()
        assert r.data_source == "live"
        assert r.regime == HMMRegime.RISK_ON
        assert r.regime != HMMRegime.RISK_OFF
        assert r.regime_multiplier == _REGIME_MULTIPLIERS[r.regime]

    async def test_recent_crash_is_risk_off(self, market):
        market.set_closes("SPY", _ends_in_crash())
        svc = HMMRegimeService()
        r = await svc.get_regime()
        assert r.data_source == "live"
        assert r.regime == HMMRegime.RISK_OFF
        # risk-off probability should dominate the risk-on probability.
        assert r.regime_probs[0] > r.regime_probs[2]
        assert r.regime_multiplier == _REGIME_MULTIPLIERS[r.regime]

    async def test_probs_sum_to_one(self, market):
        market.set_closes("SPY", choppy_series(n=500, noise=0.01))
        svc = HMMRegimeService()
        r = await svc.get_regime()
        assert sum(r.regime_probs) == pytest.approx(1.0, abs=1e-4)
        assert 0.0 <= r.confidence <= 1.0
        assert r.days_in_regime >= 1

    async def test_missing_spy_returns_default(self, market):
        svc = HMMRegimeService()
        r = await svc.get_regime()
        # No SPY data → safe default (NEUTRAL, multiplier intact)
        assert r.regime == HMMRegime.NEUTRAL
        assert r.regime_multiplier == 0.7

    async def test_cache_reuse(self, market):
        market.set_closes("SPY", trending_series(n=400, daily_drift=0.0006))
        svc = HMMRegimeService()
        first = await svc.get_regime()
        second = await svc.get_regime()
        assert first is second

    def test_singleton(self):
        assert get_hmm_regime_service() is get_hmm_regime_service()
