"""Tests for the PatchTST transformer trend model (NumPy analytical path)."""

import numpy as np
import pytest

from app.services.transformer_trend import (
    TransformerTrendService,
    _compute_attention_signal_numpy,
    _compute_features,
    get_transformer_service,
)
from tests.conftest import make_ohlcv, trending_series, choppy_series


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

class TestFeatureExtraction:
    def test_shape_and_channels(self):
        df = make_ohlcv(trending_series(n=150))
        feats = _compute_features(df)
        assert feats is not None
        assert feats.shape[1] == 8          # 8 channels
        assert feats.shape[0] == 150
        assert np.isfinite(feats).all()      # nan/inf scrubbed

    def test_short_history_returns_none(self):
        df = make_ohlcv(trending_series(n=20))
        assert _compute_features(df) is None


# ---------------------------------------------------------------------------
# Analytical (NumPy) attention signal
# ---------------------------------------------------------------------------

class TestAnalyticalAttention:
    def test_positive_returns_give_positive_signal(self):
        feats = np.zeros((128, 8))
        feats[:, 0] = 0.01          # uniformly positive returns channel
        signal, attn, conf = _compute_attention_signal_numpy(feats, patch_len=8)
        assert signal > 0
        assert -1.0 <= signal <= 1.0

    def test_negative_returns_give_negative_signal(self):
        feats = np.zeros((128, 8))
        feats[:, 0] = -0.01
        signal, attn, conf = _compute_attention_signal_numpy(feats, patch_len=8)
        assert signal < 0

    def test_attention_weights_sum_to_one(self):
        feats = np.random.default_rng(0).normal(0, 0.01, (128, 8))
        _, attn, _ = _compute_attention_signal_numpy(feats, patch_len=8)
        assert attn.sum() == pytest.approx(1.0, abs=1e-6)
        assert (attn >= 0).all()

    def test_recency_weighting_is_monotonic(self):
        """Most recent patch should carry the highest attention weight."""
        feats = np.zeros((128, 8))
        _, attn, _ = _compute_attention_signal_numpy(feats, patch_len=8)
        assert attn[-1] == attn.max()

    def test_confidence_high_when_consistent(self):
        feats = np.zeros((128, 8))
        feats[:, 0] = 0.01          # every patch positive → high confidence
        _, _, conf = _compute_attention_signal_numpy(feats, patch_len=8)
        assert conf == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

class TestTransformerService:
    async def test_uptrend_signal_positive(self, market):
        market.set_closes("UP", trending_series(n=200, daily_drift=0.01, noise=0.002))
        svc = TransformerTrendService()
        r = await svc.analyze("UP")
        assert r.data_source == "live"
        assert r.transformer_signal > 0
        assert r.n_patches > 0
        assert -1.0 <= r.transformer_signal <= 1.0

    async def test_attention_weights_length_matches_patches(self, market):
        market.set_closes("X", trending_series(n=200))
        svc = TransformerTrendService()
        r = await svc.analyze("X")
        assert len(r.attention_weights) == r.n_patches
        assert len(r.patch_contributions) == r.n_patches

    async def test_insufficient_data(self, market):
        market.set_closes("SHORT", trending_series(n=45))  # < SEQUENCE_LEN (128)
        svc = TransformerTrendService()
        r = await svc.analyze("SHORT")
        assert r.transformer_signal == 0.0
        assert r.signal == "HOLD"

    async def test_mode_is_analytical_without_torch_checkpoint(self, market):
        market.set_closes("M", choppy_series(n=200))
        svc = TransformerTrendService()
        r = await svc.analyze("M")
        assert r.model_mode == "analytical"

    def test_singleton(self):
        assert get_transformer_service() is get_transformer_service()
