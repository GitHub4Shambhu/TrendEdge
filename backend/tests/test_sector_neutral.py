"""Tests for sector-neutral cross-sectional momentum."""

import numpy as np
import pytest

from app.services.sector_neutral import (
    SectorNeutralMomentumService,
    SectorNeutralResult,
    get_sector,
    get_sector_neutral_service,
)
from tests.conftest import trending_series


# ---------------------------------------------------------------------------
# Sector mapping
# ---------------------------------------------------------------------------

class TestSectorMap:
    def test_known_symbols(self):
        assert get_sector("AAPL") == "Technology"
        assert get_sector("JPM") == "Financials"
        assert get_sector("XOM") == "Energy"

    def test_case_insensitive(self):
        assert get_sector("aapl") == "Technology"

    def test_unknown_symbol_is_other(self):
        assert get_sector("ZZZZ") == "Other"


# ---------------------------------------------------------------------------
# Z-score math (operate on the pure transform, no network)
# ---------------------------------------------------------------------------

class TestZScoreMath:
    def _make_results(self):
        # Two sectors, three names each, with distinct raw momentum scores.
        data = [
            ("AAPL", "Technology", 30.0),
            ("MSFT", "Technology", 20.0),
            ("NVDA", "Technology", 10.0),
            ("JPM", "Financials", 6.0),
            ("BAC", "Financials", 4.0),
            ("WFC", "Financials", 2.0),
        ]
        return [
            SectorNeutralResult(symbol=s, sector=sec, raw_score=score)
            for s, sec, score in data
        ]

    def test_within_sector_zscore_centres_each_sector(self):
        svc = SectorNeutralMomentumService()
        uni = svc._apply_sector_neutral_zscores(self._make_results())
        by_sector = {}
        for r in uni.results:
            by_sector.setdefault(r.sector, []).append(r.sector_z)
        # Each sector's z-scores should be ~mean 0.
        for sector, zs in by_sector.items():
            assert np.mean(zs) == pytest.approx(0.0, abs=1e-6)

    def test_top_of_each_sector_has_highest_z(self):
        svc = SectorNeutralMomentumService()
        uni = svc._apply_sector_neutral_zscores(self._make_results())
        by_sym = {r.symbol: r for r in uni.results}
        assert by_sym["AAPL"].sector_z > by_sym["NVDA"].sector_z   # 30 > 10 within Tech
        assert by_sym["JPM"].sector_z > by_sym["WFC"].sector_z     # 6 > 2 within Fin

    def test_sector_neutrality_removes_sector_bias(self):
        """
        Tech has much larger absolute momentum than Financials, but after
        sector-neutralisation the top name in *each* sector ranks similarly
        within its own sector (rank 1).
        """
        svc = SectorNeutralMomentumService()
        uni = svc._apply_sector_neutral_zscores(self._make_results())
        by_sym = {r.symbol: r for r in uni.results}
        assert by_sym["AAPL"].sector_rank == 1
        assert by_sym["JPM"].sector_rank == 1

    def test_blended_z_uses_alpha(self):
        svc = SectorNeutralMomentumService()
        uni = svc._apply_sector_neutral_zscores(self._make_results())
        for r in uni.results:
            expected = svc.ALPHA * r.sector_z + (1 - svc.ALPHA) * r.cross_z
            assert r.blended_z == pytest.approx(round(expected, 4), abs=1e-4)

    def test_signals_assigned_by_rank(self):
        svc = SectorNeutralMomentumService()
        uni = svc._apply_sector_neutral_zscores(self._make_results())
        signals = {r.signal for r in uni.results}
        assert "BUY" in signals       # top names
        assert "SELL" in signals      # bottom names

    def test_empty_input(self):
        svc = SectorNeutralMomentumService()
        uni = svc._apply_sector_neutral_zscores([])
        assert uni.results == []


# ---------------------------------------------------------------------------
# Raw score / ROC
# ---------------------------------------------------------------------------

class TestRawScore:
    async def test_uptrend_positive_raw_score(self, market):
        market.set_closes("AAPL", trending_series(n=320, daily_drift=0.004))
        svc = SectorNeutralMomentumService()
        r = svc._fetch_raw_score("AAPL")
        assert r is not None
        assert r.raw_score > 0
        assert r.roc_3m > 0
        assert r.sector == "Technology"

    async def test_short_history_returns_none(self, market):
        market.set_closes("AAPL", trending_series(n=40))
        svc = SectorNeutralMomentumService()
        assert svc._fetch_raw_score("AAPL") is None

    async def test_universe_end_to_end(self, market):
        market.set_closes("AAPL", trending_series(n=320, daily_drift=0.005))
        market.set_closes("MSFT", trending_series(n=320, daily_drift=0.003, seed=2))
        market.set_closes("JPM", trending_series(n=320, daily_drift=0.001, seed=3))
        svc = SectorNeutralMomentumService()
        uni = await svc.analyze_universe(["AAPL", "MSFT", "JPM"])
        assert len(uni.results) == 3
        assert "Technology" in uni.sector_stats

    def test_singleton(self):
        assert get_sector_neutral_service() is get_sector_neutral_service()
