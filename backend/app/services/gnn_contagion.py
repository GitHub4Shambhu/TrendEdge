"""
TrendEdge Backend - Graph Neural Network Sector Contagion Propagation

Models momentum contagion across correlated stocks using a 2-layer Graph
Convolutional Network (GCN).

Design
------
Nodes:   Each stock in the universe.
Edges:   Pairwise |correlation| > 0.40 over rolling 60-day return window.
Features per node: [momentum_signal, ofi_score, volume_ratio, realised_vol]

GCN message passing (2 layers):
    H^(l+1) = ReLU( A_norm @ H^(l) @ W^(l) )
where A_norm = D^{-1/2} (A + I) D^{-1/2}  (symmetric normalised adjacency)

Effect: a breakout in NVDA propagates a dampened signal to correlated peers
(AMD, SMCI, TSM, etc.) even before they individually break out.

PyTorch-optional: falls back to pure-NumPy GCN if torch is unavailable.

Output per node
---------------
- propagated_signal:  GCN-updated score ∈ [-1, +1]
- original_signal:    input signal before propagation
- contagion_score:    |propagated - original| (influence of neighbours)
- top_influencers:    up to 3 strongest-correlated neighbour symbols
- influence_weights:  weights of those neighbours
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# GCN (PyTorch)
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:

    class GCNLayer(nn.Module):
        """Single Graph Convolutional layer: H' = ReLU(A_norm H W)."""

        def __init__(self, in_features: int, out_features: int):
            super().__init__()
            self.weight = nn.Parameter(torch.empty(in_features, out_features))
            nn.init.xavier_uniform_(self.weight)

        def forward(self, x: "torch.Tensor", adj: "torch.Tensor") -> "torch.Tensor":
            support = x @ self.weight
            out = adj @ support
            return torch.relu(out)


    class StockGNN(nn.Module):
        """2-layer GCN with residual connection on node features."""

        def __init__(self, in_features: int = 4, hidden: int = 8, out_features: int = 1):
            super().__init__()
            self.layer1 = GCNLayer(in_features, hidden)
            self.layer2 = GCNLayer(hidden, out_features)
            self.skip = nn.Linear(in_features, out_features, bias=False)

        def forward(self, x: "torch.Tensor", adj: "torch.Tensor") -> "torch.Tensor":
            h = self.layer1(x, adj)
            out = self.layer2(h, adj)
            skip = torch.tanh(self.skip(x))
            return torch.tanh(out + skip)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GNNNodeResult:
    """GNN result for a single node (stock)."""
    symbol: str

    propagated_signal: float = 0.0    # after GCN propagation
    original_signal: float = 0.0     # before propagation
    contagion_score: float = 0.0     # |propagated - original|

    degree: int = 0                  # number of correlated neighbours
    avg_neighbour_signal: float = 0.0
    top_influencers: List[str] = field(default_factory=list)
    influence_weights: List[float] = field(default_factory=list)

    signal: str = "HOLD"


@dataclass
class GNNGraphResult:
    """Full GNN propagation result for the universe."""
    nodes: List[GNNNodeResult] = field(default_factory=list)
    n_edges: int = 0
    avg_correlation: float = 0.0
    most_connected_symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Graph construction helpers
# ---------------------------------------------------------------------------

def _build_adjacency(corr_matrix: np.ndarray, threshold: float = 0.40) -> np.ndarray:
    """
    Build symmetrically normalised adjacency matrix from correlation matrix.

    A_norm = D^{-1/2} (A + I) D^{-1/2}
    where A[i,j] = 1 if |corr[i,j]| > threshold and i != j.
    """
    n = corr_matrix.shape[0]
    A = (np.abs(corr_matrix) > threshold).astype(float)
    np.fill_diagonal(A, 0.0)    # no self-loops (added below via +I)
    A_tilde = A + np.eye(n)     # add self-connections

    degree = A_tilde.sum(axis=1)
    D_inv_sqrt = np.diag(1.0 / (np.sqrt(degree) + 1e-8))
    A_norm = D_inv_sqrt @ A_tilde @ D_inv_sqrt
    return A_norm


def _gcn_numpy(H: np.ndarray, A_norm: np.ndarray) -> np.ndarray:
    """
    2-layer GCN forward pass in pure NumPy (no torch required).

    Uses random-but-deterministic Xavier weights (seeded by graph size).
    """
    n, d_in = H.shape
    d_hidden, d_out = 8, 1

    rng = np.random.default_rng(seed=n * d_in)
    W1 = rng.standard_normal((d_in, d_hidden)) * np.sqrt(2.0 / (d_in + d_hidden))
    W2 = rng.standard_normal((d_hidden, d_out)) * np.sqrt(2.0 / (d_hidden + d_out))
    W_skip = rng.standard_normal((d_in, d_out)) * np.sqrt(2.0 / (d_in + d_out))

    H1 = np.maximum(A_norm @ H @ W1, 0)          # ReLU
    H2 = A_norm @ H1 @ W2
    skip = np.tanh(H @ W_skip)
    out = np.tanh(H2 + skip)
    return out.flatten()


# ---------------------------------------------------------------------------
# GNN Contagion Service
# ---------------------------------------------------------------------------

class GNNContagionService:
    """
    Propagates momentum signals through a correlation-based stock graph.

    The service:
    1. Fetches 60-day return history for all symbols.
    2. Builds pairwise correlation matrix.
    3. Constructs normalised adjacency (|corr| > 0.40 threshold).
    4. Runs 2-layer GCN to propagate signals.
    5. Returns per-node propagated signals and influence metadata.

    Cache: correlation matrix is cached for 1 day; reused if ≥80% symbol overlap.
    """

    _CORR_LOOKBACK = 60     # days for correlation estimation
    _EDGE_THRESHOLD = 0.40  # minimum |correlation| for an edge
    _CACHE_TTL_HOURS = 24

    def __init__(self):
        self._corr_cache: Optional[Tuple[np.ndarray, List[str], datetime]] = None
        self._result_cache: Optional[Tuple[GNNGraphResult, datetime]] = None
        self._result_ttl_minutes = 30
        self._executor = ThreadPoolExecutor(max_workers=4)

    async def propagate(
        self,
        signals: Dict[str, float],
        extra_features: Optional[Dict[str, List[float]]] = None,
    ) -> GNNGraphResult:
        """
        Propagate momentum signals through the correlation graph.

        Parameters
        ----------
        signals:        {symbol: signal_value} pre-GNN scores in [-1, +1]
        extra_features: optional {symbol: [feat1, feat2, feat3]} additional node features
        """
        symbols = list(signals.keys())
        if not symbols:
            return GNNGraphResult()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor, self._compute, symbols, signals, extra_features or {}
        )
        return result

    def _compute(
        self,
        symbols: List[str],
        signals: Dict[str, float],
        extra_features: Dict[str, List[float]],
    ) -> GNNGraphResult:
        try:
            # Fetch / reuse correlation matrix
            corr_matrix, valid_symbols = self._get_correlation(symbols)
            if corr_matrix is None or len(valid_symbols) < 2:
                return self._fallback_result(signals)

            n = len(valid_symbols)
            A_norm = _build_adjacency(corr_matrix, self._EDGE_THRESHOLD)

            # Build node feature matrix H: (N, 4)
            H = np.zeros((n, 4))
            for i, sym in enumerate(valid_symbols):
                H[i, 0] = float(signals.get(sym, 0.0))
                extras = extra_features.get(sym, [0.0, 0.0, 0.0])
                for j, v in enumerate(extras[:3]):
                    H[i, j + 1] = float(v)

            # Normalise H columns
            col_std = np.std(H, axis=0) + 1e-8
            H_norm = H / col_std

            # Run GCN
            if _TORCH_AVAILABLE:
                gnn = StockGNN(in_features=4, hidden=8, out_features=1)
                with torch.no_grad():
                    x = torch.tensor(H_norm, dtype=torch.float32)
                    adj = torch.tensor(A_norm, dtype=torch.float32)
                    out = gnn(x, adj).numpy().flatten()
            else:
                out = _gcn_numpy(H_norm, A_norm)

            # Assemble node results
            nodes = []
            raw_A = (np.abs(corr_matrix) > self._EDGE_THRESHOLD).astype(float)
            np.fill_diagonal(raw_A, 0.0)

            for i, sym in enumerate(valid_symbols):
                propagated = float(np.tanh(out[i]))
                original = float(signals.get(sym, 0.0))
                contagion = float(abs(propagated - original))

                # Top influencers: strongest correlated neighbours
                neighbours = np.where(raw_A[i] > 0)[0]
                if len(neighbours) > 0:
                    corr_weights = np.abs(corr_matrix[i, neighbours])
                    sorted_idx = np.argsort(corr_weights)[::-1][:3]
                    top_nbrs = [valid_symbols[neighbours[j]] for j in sorted_idx]
                    top_weights = [round(float(corr_weights[j]), 4) for j in sorted_idx]
                    avg_nbr_sig = float(np.mean([signals.get(valid_symbols[j], 0.0) for j in neighbours]))
                else:
                    top_nbrs, top_weights, avg_nbr_sig = [], [], 0.0

                sig = "BUY" if propagated > 0.2 else ("SELL" if propagated < -0.2 else "HOLD")

                nodes.append(GNNNodeResult(
                    symbol=sym,
                    propagated_signal=round(propagated, 4),
                    original_signal=round(original, 4),
                    contagion_score=round(contagion, 4),
                    degree=int(neighbours.sum() if len(neighbours) == 0 else len(neighbours)),
                    avg_neighbour_signal=round(avg_nbr_sig, 4),
                    top_influencers=top_nbrs,
                    influence_weights=top_weights,
                    signal=sig,
                ))

            # Graph stats
            n_edges = int(raw_A.sum() / 2)
            avg_corr = float(np.mean(np.abs(corr_matrix[np.triu_indices(n, k=1)])))
            degrees = raw_A.sum(axis=1)
            most_connected = valid_symbols[int(np.argmax(degrees))]

            return GNNGraphResult(
                nodes=nodes,
                n_edges=n_edges,
                avg_correlation=round(avg_corr, 4),
                most_connected_symbol=most_connected,
                timestamp=datetime.utcnow(),
            )

        except Exception:
            return self._fallback_result(signals)

    def _get_correlation(self, symbols: List[str]) -> Tuple[Optional[np.ndarray], List[str]]:
        """Fetch/reuse pairwise correlation matrix."""
        # Check cache reuse (≥80% symbol overlap)
        if self._corr_cache is not None:
            cached_corr, cached_syms, cached_at = self._corr_cache
            overlap = len(set(symbols) & set(cached_syms)) / max(len(symbols), 1)
            age_hours = (datetime.utcnow() - cached_at).total_seconds() / 3600
            if overlap >= 0.80 and age_hours < self._CACHE_TTL_HOURS:
                # Return subset of cached correlation
                idx = [cached_syms.index(s) for s in symbols if s in cached_syms]
                valid_syms = [cached_syms[i] for i in idx]
                if len(valid_syms) >= 2:
                    sub = cached_corr[np.ix_(idx, idx)]
                    return sub, valid_syms

        # Fetch fresh data
        price_data: Dict[str, np.ndarray] = {}
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                h = t.history(period="4mo", interval="1d")
                if h is not None and len(h) >= 30:
                    price_data[sym] = h["Close"].values.astype(float)
            except Exception:
                pass

        if len(price_data) < 2:
            return None, []

        min_len = min(len(v) for v in price_data.values())
        lookback = min(self._CORR_LOOKBACK, min_len - 1)

        ret_matrix = np.column_stack([
            np.diff(np.log(v[-lookback - 1:]))
            for v in price_data.values()
        ])
        valid_syms = list(price_data.keys())

        corr = np.corrcoef(ret_matrix.T)
        corr = np.nan_to_num(corr, nan=0.0)

        self._corr_cache = (corr, valid_syms, datetime.utcnow())
        return corr, valid_syms

    def _fallback_result(self, signals: Dict[str, float]) -> GNNGraphResult:
        """Return passthrough result (propagated = original) when graph fails."""
        nodes = []
        for sym, sig in signals.items():
            signal_str = "BUY" if sig > 0.2 else ("SELL" if sig < -0.2 else "HOLD")
            nodes.append(GNNNodeResult(
                symbol=sym,
                propagated_signal=round(float(sig), 4),
                original_signal=round(float(sig), 4),
                contagion_score=0.0,
                signal=signal_str,
            ))
        return GNNGraphResult(nodes=nodes, timestamp=datetime.utcnow())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_gnn_service: Optional[GNNContagionService] = None


def get_gnn_service() -> GNNContagionService:
    global _gnn_service
    if _gnn_service is None:
        _gnn_service = GNNContagionService()
    return _gnn_service
