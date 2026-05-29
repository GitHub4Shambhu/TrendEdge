"""Tests for the unified 7-technique trend orchestrator."""

import numpy as np
import pytest

from app.services.unified_trend import (
    UnifiedTrendService,
    UnifiedTrendScore,
    get_unified_trend_service,
    _WEIGHTS,
)
from app.services.kalman_trend import KalmanTrendResult
from app.services.hmm_regime import HMMRegimeResult, HMMRegime
from app.services.transformer_trend import TransformerTrendResult
from app.services.sector_neutral import SectorNeutralResult
from app.services.crash_protection import CrashProtectionResult, VolatilityRegime
from app.services.order_flow import OFIResult
from tests.conftest import trending_series, choppy_series


# ---------------------------------------------------------------------------
# Ensemble weights
# ---------------------------------------------------------------------------

class TestWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-6

    def test_all_weights_positive(self):
        assert all(w > 0 for w in _WEIGHTS.values())


# ---------------------------------------------------------------------------
# Combination logic (synthetic inputs, no network)
# ---------------------------------------------------------------------------

def _bull_inputs(symbol="AAPL"):
    kalman = KalmanTrendResult(symbol=symbol, kalman_signal=0.8,
                               trend_direction="UP", price=150.0)
    regime = HMMRegimeResult(regime=HMMRegime.RISK_ON, regime_multiplier=1.0)
    tst = TransformerTrendResult(symbol=symbol, transformer_signal=0.7)
    sector = SectorNeutralResult(symbol=symbol, sector="Technology",
                                 blended_z=2.0, sector_rank=1, universe_rank=1)
    crash = CrashProtectionResult(symbol=symbol, exposure_scalar=1.0,
                                  vol_regime=VolatilityRegime.NORMAL)
    ofi = OFIResult(symbol=symbol, ofi_score=0.6)
    return kalman, regime, tst, sector, crash, ofi


class TestCombine:
    def test_strong_bull_yields_buy(self):
        svc = UnifiedTrendService()
        kalman, regime, tst, sector, crash, ofi = _bull_inputs()
        score = svc._combine(
            symbol="AAPL", kalman=kalman, regime=regime, tst=tst,
            sector=sector, crash=crash, ofi=ofi, gnn_node=None, advanced=None,
        )
        assert score.final_score > 0.25
        assert score.signal == "BUY"
        assert -1.0 <= score.final_score <= 1.0
        assert 0.0 <= score.confidence <= 1.0

    def test_risk_off_blocks_buy(self):
        svc = UnifiedTrendService()
        kalman, _, tst, sector, crash, ofi = _bull_inputs()
        regime = HMMRegimeResult(regime=HMMRegime.RISK_OFF, regime_multiplier=0.3)
        score = svc._combine(
            symbol="AAPL", kalman=kalman, regime=regime, tst=tst,
            sector=sector, crash=crash, ofi=ofi, gnn_node=None, advanced=None,
        )
        # Even with bullish components, RISK_OFF regime must prevent a BUY.
        assert score.signal != "BUY"

    def test_danger_vol_blocks_buy(self):
        svc = UnifiedTrendService()
        kalman, regime, tst, sector, _, ofi = _bull_inputs()
        crash = CrashProtectionResult(symbol="AAPL", exposure_scalar=0.2,
                                      vol_regime=VolatilityRegime.DANGER)
        score = svc._combine(
            symbol="AAPL", kalman=kalman, regime=regime, tst=tst,
            sector=sector, crash=crash, ofi=ofi, gnn_node=None, advanced=None,
        )
        assert score.signal != "BUY"

    def test_exposure_scalar_dampens_score(self):
        svc = UnifiedTrendService()
        kalman, regime, tst, sector, _, ofi = _bull_inputs()
        full = svc._combine("AAPL", kalman, regime, tst, sector,
                            CrashProtectionResult("AAPL", exposure_scalar=1.0),
                            ofi, None, None)
        reduced = svc._combine("AAPL", kalman, regime, tst, sector,
                               CrashProtectionResult("AAPL", exposure_scalar=0.3),
                               ofi, None, None)
        assert abs(reduced.final_score) < abs(full.final_score)

    def test_regime_multiplier_dampens_score(self):
        svc = UnifiedTrendService()
        kalman, _, tst, sector, crash, ofi = _bull_inputs()
        risk_on = svc._combine("AAPL", kalman,
                               HMMRegimeResult(regime=HMMRegime.RISK_ON, regime_multiplier=1.0),
                               tst, sector, crash, ofi, None, None)
        neutral = svc._combine("AAPL", kalman,
                               HMMRegimeResult(regime=HMMRegime.NEUTRAL, regime_multiplier=0.7),
                               tst, sector, crash, ofi, None, None)
        assert abs(neutral.final_score) < abs(risk_on.final_score)

    def test_all_none_is_safe(self):
        svc = UnifiedTrendService()
        score = svc._combine("X", None, None, None, None, None, None, None, None)
        assert isinstance(score, UnifiedTrendScore)
        assert score.final_score == pytest.approx(0.0, abs=1e-6)
        assert score.signal == "HOLD"
        assert score.regime == "NEUTRAL"

    def test_techniques_used_tracked(self):
        svc = UnifiedTrendService()
        kalman, regime, tst, sector, crash, ofi = _bull_inputs()
        score = svc._combine("AAPL", kalman, regime, tst, sector, crash, ofi, None, None)
        assert "kalman_filter" in score.techniques_used
        assert "patchtst_transformer" in score.techniques_used
        assert "sector_neutral_z" in score.techniques_used
        assert "order_flow_imbalance" in score.techniques_used

    def test_strong_bear_yields_sell(self):
        svc = UnifiedTrendService()
        kalman = KalmanTrendResult(symbol="X", kalman_signal=-0.8, trend_direction="DOWN")
        regime = HMMRegimeResult(regime=HMMRegime.RISK_ON, regime_multiplier=1.0)
        tst = TransformerTrendResult(symbol="X", transformer_signal=-0.7)
        sector = SectorNeutralResult(symbol="X", blended_z=-2.0)
        crash = CrashProtectionResult(symbol="X", exposure_scalar=1.0)
        ofi = OFIResult(symbol="X", ofi_score=-0.6)
        score = svc._combine("X", kalman, regime, tst, sector, crash, ofi, None, None)
        assert score.final_score < -0.25
        assert score.signal == "SELL"


# ---------------------------------------------------------------------------
# End-to-end universe pipeline (fake yfinance for all symbols + SPY)
# ---------------------------------------------------------------------------

class TestUniversePipeline:
    async def test_analyze_universe_runs(self, market):
        market.set_closes("SPY", trending_series(n=500, daily_drift=0.0006, noise=0.004))
        market.set_closes("AAPL", trending_series(n=320, daily_drift=0.006, noise=0.003))
        market.set_closes("MSFT", trending_series(n=320, daily_drift=0.004, seed=2))
        market.set_closes("JPM", trending_series(n=320, daily_drift=-0.003, seed=3))

        svc = UnifiedTrendService()
        universe = await svc.analyze_universe(["AAPL", "MSFT", "JPM"])

        assert len(universe.scores) == 3
        # results sorted descending by final_score
        scores = [s.final_score for s in universe.scores]
        assert scores == sorted(scores, reverse=True)
        for s in universe.scores:
            assert -1.0 <= s.final_score <= 1.0
            assert s.signal in ("BUY", "SELL", "HOLD")

    async def test_analyze_symbol_runs(self, market):
        market.set_closes("SPY", trending_series(n=500, daily_drift=0.0006))
        market.set_closes("AAPL", trending_series(n=320, daily_drift=0.006, noise=0.003))
        svc = UnifiedTrendService()
        score = await svc.analyze_symbol("AAPL")
        assert score.symbol == "AAPL"
        assert -1.0 <= score.final_score <= 1.0
        assert "kalman_filter" in score.techniques_used

    def test_singleton(self):
        assert get_unified_trend_service() is get_unified_trend_service()
