"""
TrendEdge Backend - Cross-Sectional Momentum with Sector-Neutral Z-Scores

Replaces naive cross-sectional ranking with sector-neutral standardisation:

1. Assign each symbol to its GICS sector.
2. Compute raw momentum score (multi-timeframe ROC) for every symbol.
3. Z-score each symbol *within its sector*:
       z_sector = (score - sector_mean) / sector_std
4. Z-score each symbol *cross-sectionally* (across all sectors):
       z_cross = (z_sector - universe_mean) / universe_std
5. Blend:  final_rank = α * z_sector + (1-α) * z_cross  (default α = 0.6)

Why this matters
----------------
Naive momentum rankings are contaminated by sector rotations.
Sector-neutral z-scores isolate stock-specific momentum from the sector beta,
dramatically reducing crash risk during sector-driven momentum unwinds.

Output per symbol
-----------------
- raw_score:         raw multi-timeframe momentum
- sector_z:          z-score within sector
- cross_z:           z-score across all sectors
- blended_z:         final rank score
- sector:            GICS sector name
- sector_rank:       rank within sector (1 = top)
- universe_rank:     rank across full universe (1 = top)
- signal:            BUY / SELL / HOLD
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


# ---------------------------------------------------------------------------
# Sector mapping (GICS-inspired)
# ---------------------------------------------------------------------------

SECTOR_MAP: Dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "NVDA": "Technology",
    "AMD": "Technology", "INTC": "Technology", "AVGO": "Technology",
    "TXN": "Technology", "QCOM": "Technology", "AMAT": "Technology",
    "MU": "Technology", "LRCX": "Technology", "KLAC": "Technology",
    "MRVL": "Technology", "NXPI": "Technology", "MCHP": "Technology",
    "ADI": "Technology", "SNPS": "Technology", "CDNS": "Technology",
    "ANSS": "Technology", "FTNT": "Technology", "PANW": "Technology",
    "CRWD": "Technology", "ZS": "Technology", "DDOG": "Technology",
    "NET": "Technology", "OKTA": "Technology", "SNOW": "Technology",
    "CRM": "Technology", "ORCL": "Technology", "IBM": "Technology",
    "ACN": "Technology", "INTU": "Technology", "ADBE": "Technology",
    "NOW": "Technology", "WDAY": "Technology", "PLTR": "Technology",
    "COIN": "Technology",

    # Consumer Discretionary
    "AMZN": "ConsumerDiscretionary", "TSLA": "ConsumerDiscretionary",
    "HD": "ConsumerDiscretionary", "LOW": "ConsumerDiscretionary",
    "NKE": "ConsumerDiscretionary", "MCD": "ConsumerDiscretionary",
    "SBUX": "ConsumerDiscretionary", "TJX": "ConsumerDiscretionary",
    "BKNG": "ConsumerDiscretionary", "ABNB": "ConsumerDiscretionary",
    "UBER": "ConsumerDiscretionary", "LYFT": "ConsumerDiscretionary",
    "SHOP": "ConsumerDiscretionary", "MELI": "ConsumerDiscretionary",
    "ROKU": "ConsumerDiscretionary",

    # Communication Services
    "NFLX": "CommunicationServices", "CMCSA": "CommunicationServices",
    "TMUS": "CommunicationServices", "VZ": "CommunicationServices",
    "T": "CommunicationServices", "SPOT": "CommunicationServices",
    "SNAP": "CommunicationServices", "PINS": "CommunicationServices",
    "RBLX": "CommunicationServices", "MTCH": "CommunicationServices",
    "ATVI": "CommunicationServices",

    # Health Care
    "JNJ": "Healthcare", "UNH": "Healthcare", "LLY": "Healthcare",
    "ABT": "Healthcare", "TMO": "Healthcare", "DHR": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "BMY": "Healthcare",
    "AMGN": "Healthcare", "GILD": "Healthcare", "ISRG": "Healthcare",
    "SYK": "Healthcare", "BDX": "Healthcare", "BSX": "Healthcare",
    "VRTX": "Healthcare", "REGN": "Healthcare", "ZTS": "Healthcare",
    "BIIB": "Healthcare", "IDXX": "Healthcare", "DXCM": "Healthcare",

    # Financials
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials",
    "GS": "Financials", "MS": "Financials", "BLK": "Financials",
    "SCHW": "Financials", "CB": "Financials", "MMC": "Financials",
    "ICE": "Financials", "CME": "Financials", "MCO": "Financials",
    "SPGI": "Financials", "V": "Financials", "MA": "Financials",
    "AXP": "Financials", "PYPL": "Financials",

    # Industrials
    "HON": "Industrials", "UPS": "Industrials", "FDX": "Industrials",
    "BA": "Industrials", "GE": "Industrials", "CAT": "Industrials",
    "DE": "Industrials", "LMT": "Industrials", "RTX": "Industrials",
    "GD": "Industrials", "NOC": "Industrials", "EMR": "Industrials",
    "ITW": "Industrials", "UNP": "Industrials", "CSX": "Industrials",
    "ODFL": "Industrials", "CPRT": "Industrials", "PCAR": "Industrials",
    "VRSK": "Industrials",

    # Consumer Staples
    "WMT": "ConsumerStaples", "PG": "ConsumerStaples", "KO": "ConsumerStaples",
    "PEP": "ConsumerStaples", "COST": "ConsumerStaples", "MO": "ConsumerStaples",
    "PM": "ConsumerStaples", "MDLZ": "ConsumerStaples", "CL": "ConsumerStaples",
    "KHC": "ConsumerStaples", "KDP": "ConsumerStaples", "MNST": "ConsumerStaples",

    # Energy
    "XOM": "Energy", "CVX": "Energy", "EOG": "Energy", "COP": "Energy",
    "SLB": "Energy", "PXD": "Energy", "FANG": "Energy", "MPC": "Energy",
    "VLO": "Energy", "PSX": "Energy",

    # Materials
    "APD": "Materials", "SHW": "Materials", "ECL": "Materials",
    "NEM": "Materials", "FCX": "Materials", "NUE": "Materials",

    # Real Estate
    "PLD": "RealEstate", "EQIX": "RealEstate", "PSA": "RealEstate",
    "O": "RealEstate", "DLR": "RealEstate",

    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    "AEP": "Utilities", "EXC": "Utilities", "XEL": "Utilities",

    # ETFs
    "SPY": "ETF", "QQQ": "ETF", "IWM": "ETF", "DIA": "ETF",
    "XLK": "ETF", "XLF": "ETF", "XLE": "ETF", "XLV": "ETF",
    "XLI": "ETF", "XLP": "ETF", "XLU": "ETF", "XLB": "ETF",
    "XLRE": "ETF", "XLC": "ETF", "XLY": "ETF",
    "ARKK": "ETF", "TQQQ": "ETF",
}

_DEFAULT_SECTOR = "Other"


def get_sector(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), _DEFAULT_SECTOR)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SectorNeutralResult:
    """Sector-neutral momentum score for a single symbol."""
    symbol: str
    sector: str = _DEFAULT_SECTOR

    raw_score: float = 0.0

    sector_z: float = 0.0
    cross_z: float = 0.0
    blended_z: float = 0.0

    sector_rank: int = 0
    sector_size: int = 0
    universe_rank: int = 0

    roc_1m: float = 0.0
    roc_3m: float = 0.0
    roc_6m: float = 0.0
    roc_12m: float = 0.0

    signal: str = "HOLD"
    price: float = 0.0
    data_source: str = "live"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SectorNeutralUniverse:
    """Results for the entire universe."""
    results: List[SectorNeutralResult] = field(default_factory=list)
    sector_stats: Dict[str, Dict] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SectorNeutralMomentumService:
    """
    Computes sector-neutral momentum z-scores for a universe of symbols.

    Fetches 14 months of history, computes skip-month ROC at 4 timeframes,
    then applies 2-level z-scoring: within-sector then across universe.
    """

    ALPHA = 0.6

    ROC_WEIGHTS = {
        "1m":  0.25,
        "3m":  0.30,
        "6m":  0.25,
        "12m": 0.20,
    }

    def __init__(self):
        self._cache: Optional[Tuple[SectorNeutralUniverse, datetime]] = None
        self._cache_ttl_minutes = 15
        self._executor = ThreadPoolExecutor(max_workers=12)

    async def analyze_universe(self, symbols: List[str]) -> SectorNeutralUniverse:
        if self._is_cached():
            return self._cache[0]  # type: ignore

        loop = asyncio.get_event_loop()
        raw_futures = {
            s: loop.run_in_executor(self._executor, self._fetch_raw_score, s)
            for s in symbols
        }
        raw_results: Dict[str, Optional[SectorNeutralResult]] = {}
        for symbol, fut in raw_futures.items():
            try:
                raw_results[symbol] = await fut
            except Exception:
                raw_results[symbol] = None

        valid = [r for r in raw_results.values() if r is not None]
        universe = self._apply_sector_neutral_zscores(valid)
        self._cache = (universe, datetime.utcnow())
        return universe

    async def get_top_n(self, symbols: List[str], n: int = 20) -> List[SectorNeutralResult]:
        universe = await self.analyze_universe(symbols)
        sorted_results = sorted(universe.results, key=lambda r: r.blended_z, reverse=True)
        return sorted_results[:n]

    def _fetch_raw_score(self, symbol: str) -> Optional[SectorNeutralResult]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="14mo", interval="1d")
            if hist is None or len(hist) < 60:
                return None

            closes = hist["Close"].values.astype(float)
            price = float(closes[-1])

            def safe_roc(lookback_days: int) -> float:
                skip = 21
                if len(closes) < lookback_days + skip:
                    return 0.0
                end_idx = len(closes) - skip
                start_idx = end_idx - lookback_days
                if start_idx < 0:
                    return 0.0
                return float((closes[end_idx] / (closes[start_idx] + 1e-8) - 1) * 100)

            roc_1m  = safe_roc(21)
            roc_3m  = safe_roc(63)
            roc_6m  = safe_roc(126)
            roc_12m = safe_roc(252)

            raw_score = (
                self.ROC_WEIGHTS["1m"]  * roc_1m  +
                self.ROC_WEIGHTS["3m"]  * roc_3m  +
                self.ROC_WEIGHTS["6m"]  * roc_6m  +
                self.ROC_WEIGHTS["12m"] * roc_12m
            )

            return SectorNeutralResult(
                symbol=symbol,
                sector=get_sector(symbol),
                raw_score=round(raw_score, 4),
                roc_1m=round(roc_1m, 2),
                roc_3m=round(roc_3m, 2),
                roc_6m=round(roc_6m, 2),
                roc_12m=round(roc_12m, 2),
                price=round(price, 2),
                data_source="live",
                timestamp=datetime.utcnow(),
            )
        except Exception:
            return None

    def _apply_sector_neutral_zscores(
        self, results: List[SectorNeutralResult]
    ) -> SectorNeutralUniverse:
        if not results:
            return SectorNeutralUniverse()

        df = pd.DataFrame([{
            "symbol": r.symbol,
            "sector": r.sector,
            "raw_score": r.raw_score,
            "idx": i,
        } for i, r in enumerate(results)])

        sector_stats: Dict[str, Dict] = {}
        df["sector_z"] = 0.0
        for sector, grp in df.groupby("sector"):
            s_mean = grp["raw_score"].mean()
            s_std = grp["raw_score"].std() + 1e-8
            df.loc[grp.index, "sector_z"] = (grp["raw_score"] - s_mean) / s_std
            top_idx = grp["raw_score"].idxmax()
            sector_stats[str(sector)] = {
                "mean": round(float(s_mean), 4),
                "std": round(float(s_std), 4),
                "count": int(len(grp)),
                "top_symbol": str(df.loc[top_idx, "symbol"]),
            }

        cs_mean = df["sector_z"].mean()
        cs_std = df["sector_z"].std() + 1e-8
        df["cross_z"] = (df["sector_z"] - cs_mean) / cs_std

        df["blended_z"] = self.ALPHA * df["sector_z"] + (1 - self.ALPHA) * df["cross_z"]

        df["universe_rank"] = df["blended_z"].rank(ascending=False).astype(int)
        df["sector_rank"] = df.groupby("sector")["blended_z"].rank(ascending=False).astype(int)
        df["sector_size"] = df.groupby("sector")["sector"].transform("count").astype(int)

        for _, row in df.iterrows():
            r = results[int(row["idx"])]
            r.sector_z = round(float(row["sector_z"]), 4)
            r.cross_z = round(float(row["cross_z"]), 4)
            r.blended_z = round(float(row["blended_z"]), 4)
            r.universe_rank = int(row["universe_rank"])
            r.sector_rank = int(row["sector_rank"])
            r.sector_size = int(row["sector_size"])

            pct = row["universe_rank"] / len(results)
            if pct <= 0.30:
                r.signal = "BUY"
            elif pct >= 0.70:
                r.signal = "SELL"
            else:
                r.signal = "HOLD"

        return SectorNeutralUniverse(
            results=sorted(results, key=lambda r: r.blended_z, reverse=True),
            sector_stats=sector_stats,
            timestamp=datetime.utcnow(),
        )

    def _is_cached(self) -> bool:
        if self._cache is None:
            return False
        elapsed = (datetime.utcnow() - self._cache[1]).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_sector_neutral_service: Optional[SectorNeutralMomentumService] = None


def get_sector_neutral_service() -> SectorNeutralMomentumService:
    global _sector_neutral_service
    if _sector_neutral_service is None:
        _sector_neutral_service = SectorNeutralMomentumService()
    return _sector_neutral_service
