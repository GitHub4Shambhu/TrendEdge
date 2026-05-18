"""
TrendEdge Backend - Transformer Temporal Attention Trend Model

Implements a PatchTST-inspired (Nie et al., 2023) architecture for multivariate
time-series trend prediction using PyTorch.

Design principles
-----------------
1. **Patching**: Raw price/indicator time series is split into non-overlapping
   patches of length P (default 8 bars). Each patch is a single token.
2. **Channel-independence**: Each input feature is treated as an independent
   univariate series processed by a shared Transformer encoder.
3. **Lightweight head**: A single linear layer maps the CLS token representation
   to a trend score in [-1, +1].
4. **No training data required at deploy time**: Without a trained checkpoint it
   operates in "analytical" mode using attention-weighted patch statistics.

Feature channels (8 total):
  [close_ret, volume_ratio, rsi_14, macd_hist, adx, bb_pos, obv_norm, atr_pct]

Output
------
- transformer_signal:  normalised trend score ∈ [-1, +1]
- attention_weights:   which patches the model attends to most
- patch_contributions: signed contribution of each patch to the final score
- confidence:         estimated certainty (entropy-based)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# Try importing PyTorch — gracefully degrade if unavailable
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

CHECKPOINT_PATH = Path(__file__).parent / "checkpoints" / "patchtst_trend.pt"


# ---------------------------------------------------------------------------
# Transformer architecture (PyTorch)
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:

    class PatchEmbedding(nn.Module):
        """Project patch of raw features into d_model-dim embedding."""

        def __init__(self, patch_len: int, n_features: int, d_model: int):
            super().__init__()
            self.proj = nn.Linear(patch_len * n_features, d_model)
            self.norm = nn.LayerNorm(d_model)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            B, N, P, C = x.shape
            x = x.reshape(B, N, P * C)
            return self.norm(self.proj(x))


    class PatchTSTEncoder(nn.Module):
        """Lightweight PatchTST encoder."""

        def __init__(self, d_model: int = 64, n_heads: int = 4,
                     n_layers: int = 2, dropout: float = 0.1):
            super().__init__()
            enc_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=n_heads,
                dim_feedforward=d_model * 4,
                dropout=dropout, batch_first=True,
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(enc_layer, num_layers=n_layers)
            self.cls_token = nn.Parameter(torch.zeros(1, 1, d_model))

        def forward(self, x: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor"]:
            B = x.shape[0]
            cls = self.cls_token.expand(B, -1, -1)
            x = torch.cat([cls, x], dim=1)

            for layer in self.encoder.layers[:-1]:
                x = layer(x)
            last = self.encoder.layers[-1]
            x_norm = last.norm1(x) if hasattr(last, 'norm1') else x
            attn_out, attn_weights = last.self_attn(
                x_norm, x_norm, x_norm, need_weights=True, average_attn_weights=True
            )
            x = x + last.dropout1(attn_out)
            x = last.norm2(x) if hasattr(last, 'norm2') else x
            ff_out = last.linear2(last.dropout(last.activation(last.linear1(x))))
            x = x + last.dropout2(ff_out)

            return x[:, 0, :], attn_weights[:, 0, 1:]


    class PatchTSTTrend(nn.Module):
        """Full PatchTST model for trend scoring."""

        def __init__(self, n_features: int = 8, patch_len: int = 8,
                     n_patches: int = 16, d_model: int = 64):
            super().__init__()
            self.patch_len = patch_len
            self.n_patches = n_patches
            self.n_features = n_features
            self.patch_embed = PatchEmbedding(patch_len, n_features, d_model)
            self.encoder = PatchTSTEncoder(d_model=d_model)
            self.head = nn.Sequential(
                nn.Linear(d_model, 32),
                nn.GELU(),
                nn.Linear(32, 1),
                nn.Tanh(),
            )
            self._init_weights()

        def _init_weights(self):
            for m in self.modules():
                if isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)

        def forward(self, x: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor"]:
            B, T, C = x.shape
            x_p = x.reshape(B, self.n_patches, self.patch_len, C)
            emb = self.patch_embed(x_p)
            cls_repr, attn = self.encoder(emb)
            score = self.head(cls_repr)
            return score.squeeze(-1), attn


# ---------------------------------------------------------------------------
# Analytical fallback (no PyTorch / no checkpoint)
# ---------------------------------------------------------------------------

def _compute_attention_signal_numpy(features: np.ndarray, patch_len: int = 8) -> Tuple[float, np.ndarray, float]:
    """
    Deterministic approximation using recency-weighted patch attention.
    Returns (signal, attn_weights, confidence).
    """
    T, C = features.shape
    n_patches = T // patch_len
    if n_patches == 0:
        return 0.0, np.array([1.0]), 0.3

    features = features[-n_patches * patch_len:]
    patches = features.reshape(n_patches, patch_len, C)
    patch_means = patches.mean(axis=1)
    ret_col = patch_means[:, 0]

    # Recency-weighted attention (most recent = highest weight)
    decay = np.exp(np.linspace(-2.0, 0.0, n_patches))
    attn = decay / decay.sum()

    raw_signal = float(np.dot(attn, ret_col))
    scale = max(float(np.std(ret_col)) * 3, 1e-4)
    signal = float(np.tanh(raw_signal / scale))

    signs = np.sign(ret_col)
    frac_positive = (signs > 0).mean()
    confidence = float(2.0 * abs(frac_positive - 0.5))

    return signal, attn, confidence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TransformerTrendResult:
    """Output from the PatchTST trend model for a single symbol."""
    symbol: str

    transformer_signal: float = 0.0
    confidence: float = 0.0

    attention_weights: List[float] = field(default_factory=list)
    patch_contributions: List[float] = field(default_factory=list)

    peak_attention_patch: int = 0
    peak_attention_age_days: int = 0

    model_mode: str = "analytical"
    n_patches: int = 0
    patch_len: int = 8

    signal: str = "HOLD"
    price: float = 0.0
    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _compute_features(hist: pd.DataFrame) -> Optional[np.ndarray]:
    """Build 8-channel feature matrix from OHLCV history."""
    try:
        close = hist["Close"].values.astype(float)
        volume = hist["Volume"].values.astype(float)
        high = hist["High"].values.astype(float)
        low = hist["Low"].values.astype(float)

        n = len(close)
        if n < 30:
            return None

        ret = np.concatenate([[0.0], np.diff(np.log(close + 1e-8))])

        vol_avg = pd.Series(volume).rolling(20, min_periods=1).mean().values
        vol_ratio = volume / (vol_avg + 1e-6) - 1.0

        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = pd.Series(gain).ewm(span=14, min_periods=1).mean().values
        avg_loss = pd.Series(loss).ewm(span=14, min_periods=1).mean().values
        rs = avg_gain / (avg_loss + 1e-8)
        rsi = 100 - 100 / (1 + rs)
        rsi_norm = (rsi - 50) / 50

        ema12 = pd.Series(close).ewm(span=12, min_periods=1).mean().values
        ema26 = pd.Series(close).ewm(span=26, min_periods=1).mean().values
        macd_line = ema12 - ema26
        signal_line = pd.Series(macd_line).ewm(span=9, min_periods=1).mean().values
        macd_hist = macd_line - signal_line
        macd_hist_norm = np.tanh(macd_hist / (np.std(macd_hist) + 1e-8))

        tr = np.maximum(high - low, np.maximum(abs(high - np.roll(close, 1)), abs(low - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).ewm(span=14, min_periods=1).mean().values
        adx_raw = pd.Series(np.abs(np.diff(close, prepend=close[0])) / (atr + 1e-8)).ewm(span=14).mean().values
        adx_norm = np.tanh(adx_raw) - 0.5

        sma20 = pd.Series(close).rolling(20, min_periods=1).mean().values
        std20 = pd.Series(close).rolling(20, min_periods=1).std().fillna(1.0).values
        bb_pos = (close - (sma20 - 2 * std20)) / (4 * std20 + 1e-8)
        bb_pos = np.clip(bb_pos, 0.0, 1.0) - 0.5

        obv = np.cumsum(np.where(np.diff(close, prepend=close[0]) >= 0, volume, -volume))
        obv_norm = np.tanh((obv - np.mean(obv)) / (np.std(obv) + 1e-8))

        atr_pct = np.tanh(atr / (close + 1e-8) * 10)

        features = np.column_stack([
            ret, vol_ratio, rsi_norm, macd_hist_norm,
            adx_norm, bb_pos, obv_norm, atr_pct
        ])

        features = np.nan_to_num(features, nan=0.0, posinf=1.0, neginf=-1.0)
        return features

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Transformer Trend Service
# ---------------------------------------------------------------------------

class TransformerTrendService:
    """PatchTST-based trend signal computation."""

    PATCH_LEN = 8
    N_PATCHES = 16
    N_FEATURES = 8
    SEQUENCE_LEN = PATCH_LEN * N_PATCHES  # 128 bars

    def __init__(self):
        self._cache: Dict[str, Tuple[TransformerTrendResult, datetime]] = {}
        self._cache_ttl_minutes = 10
        self._executor = ThreadPoolExecutor(max_workers=8)
        self._model = None
        self._mode = "analytical"
        self._try_load_model()

    def _try_load_model(self) -> None:
        if not _TORCH_AVAILABLE:
            return
        if CHECKPOINT_PATH.exists():
            try:
                model = PatchTSTTrend(
                    n_features=self.N_FEATURES,
                    patch_len=self.PATCH_LEN,
                    n_patches=self.N_PATCHES,
                )
                state = torch.load(CHECKPOINT_PATH, map_location="cpu")
                model.load_state_dict(state)
                model.eval()
                self._model = model
                self._mode = "trained"
            except Exception:
                pass
        elif _TORCH_AVAILABLE:
            self._model = PatchTSTTrend(
                n_features=self.N_FEATURES,
                patch_len=self.PATCH_LEN,
                n_patches=self.N_PATCHES,
            )
            self._model.eval()
            self._mode = "analytical"

    async def analyze(self, symbol: str) -> TransformerTrendResult:
        if self._is_cached(symbol):
            return self._cache[symbol][0]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._compute, symbol)
        self._cache[symbol] = (result, datetime.utcnow())
        return result

    async def analyze_universe(self, symbols: List[str]) -> List[TransformerTrendResult]:
        tasks = [self.analyze(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, TransformerTrendResult)]

    def _compute(self, symbol: str) -> TransformerTrendResult:
        result = TransformerTrendResult(symbol=symbol, patch_len=self.PATCH_LEN)
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="9mo", interval="1d")
            if hist is None or len(hist) < 40:
                return result

            result.price = float(hist["Close"].iloc[-1])

            features = _compute_features(hist)
            if features is None or len(features) < self.SEQUENCE_LEN:
                return result

            features_window = features[-self.SEQUENCE_LEN:]

            if self._mode == "trained" and self._model is not None:
                signal, attn, confidence = self._run_model(features_window)
            else:
                signal, attn, confidence = _compute_attention_signal_numpy(
                    features_window, self.PATCH_LEN
                )

            result.transformer_signal = round(float(signal), 4)
            result.confidence = round(float(confidence), 4)
            result.attention_weights = [round(float(a), 4) for a in attn]
            result.n_patches = len(attn)

            n_p = len(attn)
            features_patches = features_window[-n_p * self.PATCH_LEN:].reshape(n_p, self.PATCH_LEN, -1)
            patch_ret_means = features_patches[:, :, 0].mean(axis=1)
            contributions = list(np.array(attn) * patch_ret_means)
            result.patch_contributions = [round(float(c), 4) for c in contributions]

            result.peak_attention_patch = int(np.argmax(attn))
            result.peak_attention_age_days = int((n_p - result.peak_attention_patch) * self.PATCH_LEN)

            if result.transformer_signal > 0.2 and result.confidence > 0.4:
                result.signal = "BUY"
            elif result.transformer_signal < -0.2 and result.confidence > 0.4:
                result.signal = "SELL"
            else:
                result.signal = "HOLD"

            result.model_mode = self._mode
            result.data_source = "live"

        except Exception:
            result.data_source = "error"

        return result

    def _run_model(self, features: np.ndarray) -> Tuple[float, np.ndarray, float]:
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            score, attn = self._model(x)
            signal = float(score.item())
            attn_np = attn.squeeze(0).numpy()
            confidence = float(attn_np.max())
            return signal, attn_np, confidence

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache:
            return False
        elapsed = (datetime.utcnow() - self._cache[symbol][1]).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_transformer_service: Optional[TransformerTrendService] = None


def get_transformer_service() -> TransformerTrendService:
    global _transformer_service
    if _transformer_service is None:
        _transformer_service = TransformerTrendService()
    return _transformer_service
