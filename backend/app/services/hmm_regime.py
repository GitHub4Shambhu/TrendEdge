"""
TrendEdge Backend - Hidden Markov Model Regime Detector

Replaces the rule-based (QQQ vs 200DMA) regime filter with a probabilistic
3-state Hidden Markov Model trained on recent market data.

Model design
------------
Observation sequence:  daily features derived from SPY
    [daily_return, rolling_vol_20d, volume_ratio]

Hidden states (3-state):
    State 0: RISK-OFF  (bear / crisis)  — negative drift, high vol
    State 1: NEUTRAL   (sideways)       — near-zero drift, moderate vol
    State 2: RISK-ON   (bull / trending)— positive drift, low/moderate vol

Algorithm: Baum-Welch EM fitted on a rolling 252-day window, then
Viterbi decoding for the most likely current regime.

Output
------
- regime:           RISK_ON / NEUTRAL / RISK_OFF
- regime_probs:     [p_risk_off, p_neutral, p_risk_on]
- confidence:       max(regime_probs)
- days_in_regime:   consecutive days in current regime
- transition_risk:  probability of switching regime next day
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Regime enum
# ---------------------------------------------------------------------------

class HMMRegime(str, Enum):
    RISK_ON  = "RISK_ON"
    NEUTRAL  = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


# ---------------------------------------------------------------------------
# Lightweight Gaussian HMM (numpy-only, no hmmlearn required)
# ---------------------------------------------------------------------------

class GaussianHMM:
    """
    3-state Gaussian HMM with diagonal covariance.
    Trained via Baum-Welch EM.  Decodes via Viterbi.
    """

    def __init__(self, n_states: int = 3, n_iter: int = 50, tol: float = 1e-4):
        self.n_states = n_states
        self.n_iter = n_iter
        self.tol = tol
        self.means_: Optional[np.ndarray] = None
        self.covars_: Optional[np.ndarray] = None
        self.transmat_: Optional[np.ndarray] = None
        self.startprob_: Optional[np.ndarray] = None

    def _emission_log_prob(self, obs: np.ndarray) -> np.ndarray:
        T, D = obs.shape
        log_probs = np.zeros((T, self.n_states))
        for k in range(self.n_states):
            diff = obs - self.means_[k]
            var = self.covars_[k] + 1e-8
            log_det = np.sum(np.log(var))
            maha = np.sum(diff ** 2 / var, axis=1)
            log_probs[:, k] = -0.5 * (D * np.log(2 * np.pi) + log_det + maha)
        return log_probs

    def _forward(self, log_emit: np.ndarray) -> Tuple[np.ndarray, float]:
        T = log_emit.shape[0]
        log_alpha = np.full((T, self.n_states), -np.inf)
        log_alpha[0] = np.log(self.startprob_ + 1e-300) + log_emit[0]
        log_transmat = np.log(self.transmat_ + 1e-300)

        for t in range(1, T):
            for j in range(self.n_states):
                log_alpha[t, j] = (
                    np.logaddexp.reduce(log_alpha[t - 1] + log_transmat[:, j])
                    + log_emit[t, j]
                )
        log_likelihood = np.logaddexp.reduce(log_alpha[-1])
        return log_alpha, log_likelihood

    def _backward(self, log_emit: np.ndarray) -> np.ndarray:
        T = log_emit.shape[0]
        log_beta = np.zeros((T, self.n_states))
        log_transmat = np.log(self.transmat_ + 1e-300)

        for t in range(T - 2, -1, -1):
            for i in range(self.n_states):
                log_beta[t, i] = np.logaddexp.reduce(
                    log_transmat[i] + log_emit[t + 1] + log_beta[t + 1]
                )
        return log_beta

    def fit(self, obs: np.ndarray) -> "GaussianHMM":
        T, D = obs.shape
        rng = np.random.default_rng(42)

        indices = rng.choice(T, self.n_states, replace=False)
        self.means_ = obs[indices].copy().astype(float)
        self.covars_ = np.tile(np.var(obs, axis=0) + 1e-4, (self.n_states, 1))
        self.transmat_ = np.ones((self.n_states, self.n_states)) / self.n_states
        self.startprob_ = np.ones(self.n_states) / self.n_states

        prev_ll = -np.inf

        for _ in range(self.n_iter):
            log_emit = self._emission_log_prob(obs)
            log_alpha, ll = self._forward(log_emit)
            log_beta = self._backward(log_emit)

            log_gamma = log_alpha + log_beta
            log_gamma -= np.logaddexp.reduce(log_gamma, axis=1, keepdims=True)
            gamma = np.exp(log_gamma)

            log_xi = np.full((T - 1, self.n_states, self.n_states), -np.inf)
            log_transmat = np.log(self.transmat_ + 1e-300)
            for t in range(T - 1):
                for i in range(self.n_states):
                    for j in range(self.n_states):
                        log_xi[t, i, j] = (
                            log_alpha[t, i] + log_transmat[i, j]
                            + log_emit[t + 1, j] + log_beta[t + 1, j]
                        )
                log_xi[t] -= np.logaddexp.reduce(log_xi[t].ravel())
            xi = np.exp(log_xi)

            self.startprob_ = gamma[0] + 1e-10
            self.startprob_ /= self.startprob_.sum()

            for k in range(self.n_states):
                denom = gamma[:, k].sum() + 1e-10
                self.means_[k] = (gamma[:, k:k+1] * obs).sum(axis=0) / denom
                diff = obs - self.means_[k]
                self.covars_[k] = (gamma[:, k:k+1] * diff ** 2).sum(axis=0) / denom + 1e-6

            trans_num = xi.sum(axis=0)
            self.transmat_ = trans_num / (trans_num.sum(axis=1, keepdims=True) + 1e-10)

            if abs(ll - prev_ll) < self.tol:
                break
            prev_ll = ll

        return self

    def predict(self, obs: np.ndarray) -> np.ndarray:
        T = obs.shape[0]
        log_emit = self._emission_log_prob(obs)
        log_transmat = np.log(self.transmat_ + 1e-300)

        viterbi = np.full((T, self.n_states), -np.inf)
        backtrack = np.zeros((T, self.n_states), dtype=int)

        viterbi[0] = np.log(self.startprob_ + 1e-300) + log_emit[0]

        for t in range(1, T):
            for j in range(self.n_states):
                scores = viterbi[t - 1] + log_transmat[:, j]
                backtrack[t, j] = np.argmax(scores)
                viterbi[t, j] = scores[backtrack[t, j]] + log_emit[t, j]

        states = np.zeros(T, dtype=int)
        states[-1] = np.argmax(viterbi[-1])
        for t in range(T - 2, -1, -1):
            states[t] = backtrack[t + 1, states[t + 1]]
        return states

    def predict_proba(self, obs: np.ndarray) -> np.ndarray:
        log_emit = self._emission_log_prob(obs)
        log_alpha, _ = self._forward(log_emit)
        log_beta = self._backward(log_emit)
        log_gamma = log_alpha + log_beta
        log_gamma -= np.logaddexp.reduce(log_gamma, axis=1, keepdims=True)
        return np.exp(log_gamma)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HMMRegimeResult:
    """Regime detection result from the HMM."""
    regime: HMMRegime = HMMRegime.NEUTRAL
    regime_probs: List[float] = field(default_factory=lambda: [0.33, 0.34, 0.33])
    # regime_probs order: [RISK_OFF, NEUTRAL, RISK_ON]

    confidence: float = 0.5
    days_in_regime: int = 0
    transition_risk: float = 0.5

    spy_return_1m: float = 0.0
    spy_volatility: float = 0.0
    breadth_pct: float = 0.5

    regime_multiplier: float = 1.0
    # RISK_ON=1.0, NEUTRAL=0.7, RISK_OFF=0.3

    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Regime Service
# ---------------------------------------------------------------------------

_REGIME_MULTIPLIERS = {
    HMMRegime.RISK_ON:  1.0,
    HMMRegime.NEUTRAL:  0.7,
    HMMRegime.RISK_OFF: 0.3,
}


class HMMRegimeService:
    """
    Fits a 3-state Gaussian HMM on SPY daily returns to classify
    the current market regime.
    """

    _LOOKBACK = 252

    def __init__(self):
        self._cache: Optional[Tuple[HMMRegimeResult, datetime]] = None
        self._cache_ttl_minutes = 60
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def get_regime(self) -> HMMRegimeResult:
        if self._is_cached():
            return self._cache[0]  # type: ignore

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._compute_regime)
        self._cache = (result, datetime.utcnow())
        return result

    def _compute_regime(self) -> HMMRegimeResult:
        result = HMMRegimeResult()
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="2y", interval="1d")
            if hist is None or len(hist) < 60:
                return result

            closes = hist["Close"].values.astype(float)
            volumes = hist["Volume"].values.astype(float)

            returns = np.diff(np.log(closes))
            vol_20 = pd.Series(returns).rolling(20).std().fillna(method="bfill").values * np.sqrt(252)
            vol_ratio = pd.Series(volumes[1:]).rolling(20).apply(
                lambda x: x[-1] / (x[:-1].mean() + 1e-6)
            ).fillna(1.0).values

            min_len = min(len(returns), len(vol_20), len(vol_ratio))
            returns = returns[-min_len:]
            vol_20 = vol_20[-min_len:]
            vol_ratio = vol_ratio[-min_len:]

            n = min(self._LOOKBACK, min_len)
            features = np.column_stack([
                returns[-n:],
                vol_20[-n:],
                vol_ratio[-n:],
            ])

            mu = features.mean(axis=0)
            sigma = features.std(axis=0) + 1e-10
            features_z = (features - mu) / sigma

            hmm = GaussianHMM(n_states=3, n_iter=60)
            hmm.fit(features_z)

            states = hmm.predict(features_z)
            proba = hmm.predict_proba(features_z)

            state_mean_returns = [returns[-n:][states == k].mean() if (states == k).any() else 0.0
                                  for k in range(3)]
            ordered = np.argsort(state_mean_returns)
            remap = {int(ordered[i]): i for i in range(3)}

            current_raw = int(states[-1])
            current_regime_idx = remap[current_raw]
            regime_enum = [HMMRegime.RISK_OFF, HMMRegime.NEUTRAL, HMMRegime.RISK_ON][current_regime_idx]

            last_proba_raw = proba[-1]
            reordered_proba = [float(last_proba_raw[ordered[i]]) for i in range(3)]

            days_in = 1
            for i in range(len(states) - 2, -1, -1):
                if remap[int(states[i])] == current_regime_idx:
                    days_in += 1
                else:
                    break

            self_trans = float(hmm.transmat_[current_raw, current_raw])
            transition_risk = 1.0 - self_trans

            spy_return_1m = float((closes[-1] / closes[-22] - 1) * 100) if len(closes) >= 22 else 0.0
            spy_vol = float(np.std(returns[-22:]) * np.sqrt(252) * 100) if len(returns) >= 22 else 0.0

            result.regime = regime_enum
            result.regime_probs = reordered_proba
            result.confidence = float(max(reordered_proba))
            result.days_in_regime = days_in
            result.transition_risk = round(transition_risk, 4)
            result.spy_return_1m = round(spy_return_1m, 2)
            result.spy_volatility = round(spy_vol, 2)
            result.regime_multiplier = _REGIME_MULTIPLIERS[regime_enum]
            result.data_source = "live"

        except Exception:
            result.data_source = "error"

        return result

    def _is_cached(self) -> bool:
        if self._cache is None:
            return False
        elapsed = (datetime.utcnow() - self._cache[1]).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_hmm_service: Optional[HMMRegimeService] = None


def get_hmm_regime_service() -> HMMRegimeService:
    global _hmm_service
    if _hmm_service is None:
        _hmm_service = HMMRegimeService()
    return _hmm_service
