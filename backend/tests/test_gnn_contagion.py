"""Tests for the GNN sector-contagion propagation."""

import numpy as np
import pytest

from app.services.gnn_contagion import (
    GNNContagionService,
    _build_adjacency,
    _gcn_numpy,
    get_gnn_service,
)
from tests.conftest import trending_series


# ---------------------------------------------------------------------------
# Adjacency construction
# ---------------------------------------------------------------------------

class TestAdjacency:
    def test_symmetric_normalised(self):
        corr = np.array([
            [1.0, 0.9, 0.1],
            [0.9, 1.0, 0.2],
            [0.1, 0.2, 1.0],
        ])
        A = _build_adjacency(corr, threshold=0.40)
        # symmetric
        np.testing.assert_allclose(A, A.T, atol=1e-8)
        # self-loops present (diagonal non-zero after +I normalisation)
        assert (np.diag(A) > 0).all()

    def test_threshold_controls_edges(self):
        corr = np.array([
            [1.0, 0.5, 0.3],
            [0.5, 1.0, 0.3],
            [0.3, 0.3, 1.0],
        ])
        # raw adjacency (pre-normalisation) reconstructed via threshold
        A_low = _build_adjacency(corr, threshold=0.2)
        A_high = _build_adjacency(corr, threshold=0.6)
        # Lower threshold ⇒ denser graph ⇒ larger total weight.
        assert A_low.sum() >= A_high.sum()

    def test_negative_correlation_creates_edge(self):
        corr = np.array([
            [1.0, -0.8],
            [-0.8, 1.0],
        ])
        A = _build_adjacency(corr, threshold=0.4)
        # |−0.8| > 0.4 → edge exists → off-diagonal normalised weight > 0
        assert A[0, 1] > 0


# ---------------------------------------------------------------------------
# NumPy GCN forward pass
# ---------------------------------------------------------------------------

class TestGCNNumpy:
    def test_output_shape_and_bounds(self):
        n = 5
        H = np.random.default_rng(0).normal(0, 1, (n, 4))
        corr = np.eye(n) + 0.5 * (np.ones((n, n)) - np.eye(n))
        A = _build_adjacency(corr, 0.4)
        out = _gcn_numpy(H, A)
        assert out.shape == (n,)
        assert np.abs(out).max() <= 1.0          # tanh-bounded

    def test_deterministic(self):
        n = 4
        H = np.ones((n, 4))
        A = _build_adjacency(np.eye(n) + 0.5, 0.4)
        out1 = _gcn_numpy(H, A)
        out2 = _gcn_numpy(H, A)
        np.testing.assert_allclose(out1, out2)


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

class TestGNNService:
    async def test_propagation_basic(self, market):
        # Two correlated names + one independent name.
        base = trending_series(n=120, daily_drift=0.003)
        market.set_closes("NVDA", base)
        market.set_closes("AMD", base * 1.02)                         # highly correlated
        market.set_closes("KO", trending_series(n=120, daily_drift=0.0, seed=99))

        svc = GNNContagionService()
        signals = {"NVDA": 0.8, "AMD": 0.0, "KO": 0.0}
        result = await svc.propagate(signals)

        assert len(result.nodes) == 3
        by_sym = {n.symbol: n for n in result.nodes}
        # all propagated signals bounded
        for n in result.nodes:
            assert -1.0 <= n.propagated_signal <= 1.0
        # NVDA & AMD should be linked as neighbours
        assert "AMD" in by_sym["NVDA"].top_influencers or "NVDA" in by_sym["AMD"].top_influencers

    async def test_graph_stats(self, market):
        base = trending_series(n=120, daily_drift=0.002)
        market.set_closes("A", base)
        market.set_closes("B", base * 1.01)
        svc = GNNContagionService()
        result = await svc.propagate({"A": 0.5, "B": -0.5})
        assert result.n_edges >= 0
        assert 0.0 <= result.avg_correlation <= 1.0
        assert result.most_connected_symbol in ("A", "B")

    async def test_empty_signals(self):
        svc = GNNContagionService()
        result = await svc.propagate({})
        assert result.nodes == []

    async def test_single_symbol_fallback(self, market):
        market.set_closes("ONLY", trending_series(n=120))
        svc = GNNContagionService()
        result = await svc.propagate({"ONLY": 0.6})
        # <2 valid symbols → passthrough fallback (propagated == original)
        assert len(result.nodes) == 1
        assert result.nodes[0].propagated_signal == pytest.approx(0.6, abs=1e-4)

    def test_singleton(self):
        assert get_gnn_service() is get_gnn_service()
