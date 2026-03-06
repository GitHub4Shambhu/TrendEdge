"""
TrendEdge Backend - Market Cap Universe Service

Curates stock symbols by market capitalization tier using Fidelity-style thresholds.
Caches market cap lookups for 24 hours.
"""

import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

import yfinance as yf


class MarketCapTier(str, Enum):
    """Market cap classification tiers (Fidelity-style thresholds)."""
    MEGA = "mega"       # > $476.85B
    LARGE = "large"     # $81.98B — $476.85B
    MEDIUM = "medium"   # $13.73B — $81.98B
    SMALL = "small"     # $3.50B — $13.73B
    MICRO = "micro"     # $0 — $3.50B


# Thresholds in dollars
TIER_THRESHOLDS: Dict[MarketCapTier, Tuple[float, float]] = {
    MarketCapTier.MEGA:   (476_850_000_000, float("inf")),
    MarketCapTier.LARGE:  (81_980_000_000, 476_850_000_000),
    MarketCapTier.MEDIUM: (13_730_000_000, 81_980_000_000),
    MarketCapTier.SMALL:  (3_500_000_000, 13_730_000_000),
    MarketCapTier.MICRO:  (0, 3_500_000_000),
}

TIER_LABELS: Dict[MarketCapTier, str] = {
    MarketCapTier.MEGA:   "Mega Cap (> $476.85B)",
    MarketCapTier.LARGE:  "Large Cap ($81.98B — $476.85B)",
    MarketCapTier.MEDIUM: "Medium Cap ($13.73B — $81.98B)",
    MarketCapTier.SMALL:  "Small Cap ($3.50B — $13.73B)",
    MarketCapTier.MICRO:  "Micro Cap (< $3.50B)",
}

# ~30 seed symbols per tier (representative stocks across sectors)
TIER_SEEDS: Dict[MarketCapTier, List[str]] = {
    MarketCapTier.MEGA: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
        "LLY", "UNH", "V", "JPM", "XOM", "MA", "JNJ", "AVGO", "PG", "HD",
        "COST", "WMT", "ORCL", "MRK", "ABBV", "CRM", "NFLX", "AMD", "PEP",
        "KO", "TMO", "ADBE",
    ],
    MarketCapTier.LARGE: [
        "ISRG", "INTU", "BKNG", "UBER", "TXN", "NOW", "QCOM", "HON", "IBM",
        "AMAT", "GE", "CAT", "BA", "LOW", "DE", "SPGI", "ADP", "SBUX",
        "ADI", "GILD", "VRTX", "MMC", "LMT", "SYK", "REGN", "CI", "CB",
        "MDLZ", "BDX", "SCHW",
    ],
    MarketCapTier.MEDIUM: [
        "PANW", "CRWD", "DDOG", "SNOW", "MELI", "ABNB", "FTNT", "ZS",
        "NET", "WDAY", "TEAM", "MDB", "MRVL", "NXPI", "ODFL", "ROST",
        "FAST", "IDXX", "CPRT", "CSGP", "DASH", "DKNG", "TTD",
        "COIN", "SNAP", "PINS", "RBLX", "SPOT", "OKTA", "VEEV",
    ],
    MarketCapTier.SMALL: [
        "U", "BILL", "PCOR", "DOCS", "BRZE", "ALRM", "CWAN", "CARG",
        "SMCI", "AFRM", "HIMS", "DUOL", "PATH", "GLBE", "CFLT",
        "APPS", "ASAN", "GTLB", "ESTC", "HOOD", "SOFI", "RIVN", "LCID",
        "NIO", "UPST", "IONQ", "JOBY", "CELH", "TMDX",
    ],
    MarketCapTier.MICRO: [
        "SNDL", "TLRY", "DNA", "GSAT", "OPEN", "CLOV",
        "BARK", "OUST", "STEM", "ARQQ", "BIRD", "NNOX",
        "MNDY", "FIGS", "EVGO", "CHPT", "BLNK", "WKHS", "GOEV",
        "QS", "MVST", "PAYO", "BTBT", "MARA", "RIOT",
        "GEVO", "ORGN", "ASTS", "AMPX", "BEEM",
    ],
}

# Display order for the frontend
TIER_ORDER: List[MarketCapTier] = [
    MarketCapTier.MEGA,
    MarketCapTier.LARGE,
    MarketCapTier.MEDIUM,
    MarketCapTier.SMALL,
    MarketCapTier.MICRO,
]


class MarketCapService:
    """Manages market-cap-based stock universes with 24h caching."""

    _CACHE_TTL = 86_400  # 24 hours in seconds

    def __init__(self) -> None:
        self._cache: Dict[str, Tuple[float, Optional[float]]] = {}  # symbol -> (timestamp, market_cap)

    def get_symbols_for_tier(self, tier: MarketCapTier) -> List[str]:
        """Return the seed symbol list for a given tier."""
        return TIER_SEEDS.get(tier, []).copy()

    def classify_symbol(self, symbol: str) -> Optional[MarketCapTier]:
        """Classify a symbol into a market cap tier using yfinance data (cached 24h)."""
        market_cap = self._get_market_cap(symbol)
        if market_cap is None:
            return None
        for tier, (low, high) in TIER_THRESHOLDS.items():
            if low <= market_cap < high:
                return tier
        return None

    def _get_market_cap(self, symbol: str) -> Optional[float]:
        """Fetch market cap for a symbol with 24h cache."""
        now = time.time()
        if symbol in self._cache:
            ts, val = self._cache[symbol]
            if now - ts < self._CACHE_TTL:
                return val
        try:
            info = yf.Ticker(symbol).info
            mc = info.get("marketCap")
            self._cache[symbol] = (now, mc)
            return mc
        except Exception:
            self._cache[symbol] = (now, None)
            return None

    @staticmethod
    def get_tier_label(tier: MarketCapTier) -> str:
        return TIER_LABELS[tier]


# Singleton
_instance: Optional[MarketCapService] = None


def get_market_cap_service() -> MarketCapService:
    global _instance
    if _instance is None:
        _instance = MarketCapService()
    return _instance
