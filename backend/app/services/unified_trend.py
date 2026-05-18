"""
TrendEdge Backend - Unified Trend Identification Service

Orchestrates all 7 advanced trend-identification techniques into a single
composite score and final signal.

Technique stack (in pipeline order)
--------------------------------------
1. Kalman Filter         – adaptive smoothed price level + velocity
2. HMM Regime            – market regime gate (RISK_ON / NEUTRAL / RISK_OFF)
3. PatchTST Transformer  – patch-level temporal attention score
4. Sector-Neutral Z      – cross-sectional sector-adjusted rank score
5. Crash Protection      – volatility-scaled exposure scalar
6. OFI Signal            – order flow imbalance (buy/sell pressure)
7. GNN Contagion         – neighbour-propagated signal correction

Ensemble weights (sum = 1.0)
--------------------------------------
    kalman_signal         0.18
    transformer_signal    0.20
    sector_neutral_z      0.20
    ofi_score             0.18
    gnn_propagated        0.14
    advanced_momentum     0.10

Post-weighting modifiers
--------------------------------------
    × regime_multiplier   (HMM: 1.0 / 0.7 / 0.3)
    × exposure_scalar     (crash protection: 0.0 – 1.5)

Final score:  tanh(raw_composite × regime_mult × exposure_scalar × 2)

Signal thresholds
--------------------------------------
    BUY  if score > +0.25 AND regime != RISK_OFF AND vol_regime != DANGER
    SELL if score < -0.25 OR  (score < 0 AND regime == RISK_OFF)
    HOLD otherwise
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import warnings

import numpy as np

from app.services.kalman_trend import get_kalman_service, KalmanTrendResult
from app.services.hmm_regime import get_hmm_regime_service, HMMRegimeResult, HMMRegime
from app.services.transformer_trend import get_transformer_service, TransformerTrendResult
from app.services.sector_neutral import get_sector_neutral_service, SectorNeutralResult
from app.services.crash_protection import (
    get_crash_protection_service, CrashProtectionResult, VolatilityRegime
)
from app.services.order_flow import get_ofi_service, OFIResult
from app.services.gnn_contagion import get_gnn_service, GNNNodeResult
from app.services.advanced_momentum import get_momentum_algorithm, MomentumFactors

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Ensemble weights
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "kalman":      0.18,
    "transformer": 0.20,
    "sector_z":    0.20,
    "ofi":         0.18,
    "gnn":         0.14,
    "advanced":    0.10,
}
assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-6, "Weights must sum to 1.0"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class UnifiedTrendScore:
    """Comprehensive trend score combining all 7 techniques."""
    symbol: str

    # Final output
    final_score: float = 0.0
    signal: str = "HOLD"
    confidence: float = 0.0

    # Component scores
    kalman_signal: float = 0.0
    transformer_signal: float = 0.0
    sector_neutral_z: float = 0.0
    ofi_score: float = 0.0
    gnn_propagated: float = 0.0
    advanced_momentum: float = 0.0

    # Modifiers
    regime: str = "NEUTRAL"
    regime_multiplier: float = 1.0
    exposure_scalar: float = 1.0
    vol_regime: str = "NORMAL"

    # Context
    kalman_trend: float = 0.0
    kalman_velocity: float = 0.0
    trend_direction: str = "NEUTRAL"
    drawdown_from_peak: float = 0.0
    trend_exhausted: bool = False

    # Sector
    sector: str = "Other"
    sector_rank: int = 0
    universe_rank: int = 0

    # GNN context
    top_influencers: List[str] = field(default_factory=list)

    # Metadata
    price: float = 0.0
    techniques_used: List[str] = field(default_factory=list)
    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UnifiedTrendUniverse:
    """Universe-level results from the unified pipeline."""
    scores: List[UnifiedTrendScore] = field(default_factory=list)
    regime: HMMRegimeResult = field(default_factory=HMMRegimeResult)
    top_buys: List[str] = field(default_factory=list)
    top_sells: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Unified service
# ---------------------------------------------------------------------------

class UnifiedTrendService:
    """
    Orchestrates all 7 trend identification techniques for a universe of symbols.

    Pipeline:
        1. Fetch regime (once for universe)
        2. Per-symbol: Kalman, Transformer, OFI, Crash Protection (parallel)
        3. Universe-level: Sector-Neutral Z-scores (needs all raw scores first)
        4. GNN propagation (needs all signals first)
        5. Combine into final score
    """

    def __init__(self):
        self._kalman   = get_kalman_service()
        self._hmm      = get_hmm_regime_service()
        self._patchtst = get_transformer_service()
        self._sector   = get_sector_neutral_service()
        self._crash    = get_crash_protection_service()
        self._ofi      = get_ofi_service()
        self._gnn      = get_gnn_service()
        self._advanced = get_momentum_algorithm()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze_symbol(self, symbol: str) -> UnifiedTrendScore:
        """Full pipeline for a single symbol (no sector-neutral, no GNN)."""
        regime_task   = self._hmm.get_regime()
        kalman_task   = self._kalman.analyze(symbol)
        tst_task      = self._patchtst.analyze(symbol)
        ofi_task      = self._ofi.analyze(symbol)
        advanced_task = self._fetch_advanced(symbol)

        regime, kalman, tst, ofi, advanced = await asyncio.gather(
            regime_task, kalman_task, tst_task, ofi_task, advanced_task
        )

        raw_proxy = kalman.kalman_signal
        crash = await self._crash.protect(symbol, raw_proxy)

        return self._combine(
            symbol=symbol,
            kalman=kalman,
            regime=regime,
            tst=tst,
            sector=None,
            crash=crash,
            ofi=ofi,
            gnn_node=None,
            advanced=advanced,
        )

    async def analyze_universe(self, symbols: List[str]) -> UnifiedTrendUniverse:
        """Full 7-technique pipeline for an entire universe."""

        # 1. Regime (shared for all symbols)
        regime = await self._hmm.get_regime()

        # 2. Per-symbol techniques in parallel
        kalman_task  = self._kalman.analyze_universe(symbols)
        tst_task     = self._patchtst.analyze_universe(symbols)
        ofi_task     = self._ofi.analyze_universe(symbols)
        sector_task  = self._sector.analyze_universe(symbols)

        kalman_results, tst_results, ofi_results, sector_universe = await asyncio.gather(
            kalman_task, tst_task, ofi_task, sector_task
        )

        kalman_map: Dict[str, KalmanTrendResult] = {r.symbol: r for r in kalman_results}
        tst_map: Dict[str, TransformerTrendResult] = {r.symbol: r for r in tst_results}
        ofi_map: Dict[str, OFIResult] = {r.symbol: r for r in ofi_results}
        sector_map: Dict[str, SectorNeutralResult] = {
            r.symbol: r for r in sector_universe.results
        }

        # 3. Build raw signals for crash protection
        raw_signals: Dict[str, float] = {
            sym: float(
                0.5 * kalman_map.get(sym, KalmanTrendResult(sym)).kalman_signal +
                0.5 * tst_map.get(sym, TransformerTrendResult(sym)).transformer_signal
            )
            for sym in symbols
        }

        # 4. Crash protection in parallel
        crash_map: Dict[str, CrashProtectionResult] = {}
        crash_tasks = {sym: self._crash.protect(sym, raw_signals[sym]) for sym in symbols}
        for sym, task in crash_tasks.items():
            try:
                crash_map[sym] = await task
            except Exception:
                crash_map[sym] = CrashProtectionResult(symbol=sym)

        # 5. Assemble per-symbol pre-GNN scores
        pre_gnn_signals: Dict[str, float] = {}
        pre_scores: Dict[str, UnifiedTrendScore] = {}

        for sym in symbols:
            score = self._combine(
                symbol=sym,
                kalman=kalman_map.get(sym),
                regime=regime,
                tst=tst_map.get(sym),
                sector=sector_map.get(sym),
                crash=crash_map.get(sym),
                ofi=ofi_map.get(sym),
                gnn_node=None,
                advanced=None,
            )
            pre_scores[sym] = score
            pre_gnn_signals[sym] = score.final_score

        # 6. GNN propagation
        extra_feats: Dict[str, List[float]] = {
            sym: [
                float(ofi_map.get(sym, OFIResult(sym)).ofi_score),
                0.0,
                float(crash_map.get(sym, CrashProtectionResult(sym)).realised_vol_10d) / 100,
            ]
            for sym in symbols
        }

        gnn_result = await self._gnn.propagate(pre_gnn_signals, extra_feats)
        gnn_map: Dict[str, GNNNodeResult] = {n.symbol: n for n in gnn_result.nodes}

        # 7. Recompute final scores with GNN correction
        final_scores: List[UnifiedTrendScore] = []
        for sym in symbols:
            gnn_node = gnn_map.get(sym)
            score = pre_scores[sym]
            if gnn_node is not None:
                score.gnn_propagated = round(float(gnn_node.propagated_signal), 4)
                score.top_influencers = gnn_node.top_influencers
                raw = (
                    _WEIGHTS["kalman"]      * score.kalman_signal +
                    _WEIGHTS["transformer"] * score.transformer_signal +
                    _WEIGHTS["sector_z"]    * score.sector_neutral_z +
                    _WEIGHTS["ofi"]         * score.ofi_score +
                    _WEIGHTS["gnn"]         * score.gnn_propagated +
                    _WEIGHTS["advanced"]    * score.advanced_momentum
                )
                raw *= score.regime_multiplier * score.exposure_scalar
                score.final_score = round(float(np.tanh(raw * 2)), 4)
                score = self._assign_signal(score)
            final_scores.append(score)

        final_scores.sort(key=lambda s: s.final_score, reverse=True)

        top_buys  = [s.symbol for s in final_scores if s.signal == "BUY"][:10]
        top_sells = [s.symbol for s in final_scores if s.signal == "SELL"][:5]

        return UnifiedTrendUniverse(
            scores=final_scores,
            regime=regime,
            top_buys=top_buys,
            top_sells=top_sells,
            timestamp=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Internal: combination logic
    # ------------------------------------------------------------------

    def _combine(
        self,
        symbol: str,
        kalman:   Optional[KalmanTrendResult],
        regime:   Optional[HMMRegimeResult],
        tst:      Optional[TransformerTrendResult],
        sector:   Optional[SectorNeutralResult],
        crash:    Optional[CrashProtectionResult],
        ofi:      Optional[OFIResult],
        gnn_node: Optional[GNNNodeResult],
        advanced: Optional[MomentumFactors],
    ) -> UnifiedTrendScore:

        score = UnifiedTrendScore(symbol=symbol)
        techniques: List[str] = []

        if kalman is not None:
            score.kalman_signal   = float(kalman.kalman_signal)
            score.kalman_trend    = float(kalman.kalman_trend)
            score.kalman_velocity = float(kalman.kalman_velocity)
            score.trend_direction = kalman.trend_direction
            score.price = max(score.price, kalman.price)
            techniques.append("kalman_filter")

        if tst is not None:
            score.transformer_signal = float(tst.transformer_signal)
            techniques.append("patchtst_transformer")

        if sector is not None:
            score.sector_neutral_z = float(np.tanh(sector.blended_z / 2.0))
            score.sector       = sector.sector
            score.sector_rank  = sector.sector_rank
            score.universe_rank = sector.universe_rank
            techniques.append("sector_neutral_z")

        if ofi is not None:
            score.ofi_score = float(ofi.ofi_score)
            techniques.append("order_flow_imbalance")

        if gnn_node is not None:
            score.gnn_propagated  = float(gnn_node.propagated_signal)
            score.top_influencers = gnn_node.top_influencers
            techniques.append("gnn_contagion")
        else:
            score.gnn_propagated = float(
                0.5 * score.kalman_signal + 0.5 * score.transformer_signal
            )

        if advanced is not None:
            score.advanced_momentum = float(advanced.composite_score)
            score.price = max(score.price, advanced.price)
            techniques.append("advanced_momentum")
        else:
            score.advanced_momentum = score.kalman_signal

        if regime is not None:
            score.regime = regime.regime.value
            score.regime_multiplier = float(regime.regime_multiplier)
        else:
            score.regime = "NEUTRAL"
            score.regime_multiplier = 0.7

        if crash is not None:
            score.exposure_scalar    = float(crash.exposure_scalar)
            score.vol_regime         = crash.vol_regime.value
            score.drawdown_from_peak = float(crash.drawdown_from_peak)
            score.trend_exhausted    = crash.trend_exhausted
        else:
            score.exposure_scalar = 1.0
            score.vol_regime = "NORMAL"

        raw_composite = (
            _WEIGHTS["kalman"]      * score.kalman_signal +
            _WEIGHTS["transformer"] * score.transformer_signal +
            _WEIGHTS["sector_z"]    * score.sector_neutral_z +
            _WEIGHTS["ofi"]         * score.ofi_score +
            _WEIGHTS["gnn"]         * score.gnn_propagated +
            _WEIGHTS["advanced"]    * score.advanced_momentum
        )

        raw_composite *= score.regime_multiplier * score.exposure_scalar
        score.final_score = round(float(np.tanh(raw_composite * 2)), 4)

        component_signs = [
            np.sign(score.kalman_signal),
            np.sign(score.transformer_signal),
            np.sign(score.ofi_score),
            np.sign(score.gnn_propagated),
            np.sign(score.sector_neutral_z),
        ]
        non_zero = [s for s in component_signs if s != 0]
        if non_zero:
            dominant = max(set(non_zero), key=non_zero.count)
            agreement = sum(1 for s in non_zero if s == dominant) / len(non_zero)
            score.confidence = round(float(agreement * abs(score.final_score)), 4)
        else:
            score.confidence = 0.0

        score.techniques_used = techniques
        score = self._assign_signal(score)
        return score

    def _assign_signal(self, score: UnifiedTrendScore) -> UnifiedTrendScore:
        regime_safe = score.regime != HMMRegime.RISK_OFF.value
        vol_safe = score.vol_regime not in ("DANGER",)

        if score.final_score > 0.25 and regime_safe and vol_safe:
            score.signal = "BUY"
        elif (score.final_score < -0.25) or (score.final_score < 0 and not regime_safe):
            score.signal = "SELL"
        else:
            score.signal = "HOLD"

        return score

    async def _fetch_advanced(self, symbol: str) -> Optional[MomentumFactors]:
        try:
            return await self._advanced.analyze_symbol(symbol)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_unified_service: Optional[UnifiedTrendService] = None


def get_unified_trend_service() -> UnifiedTrendService:
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedTrendService()
    return _unified_service
