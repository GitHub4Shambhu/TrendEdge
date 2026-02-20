"""
TrendEdge Backend - Stock Universe Management

Manages the universe of US stocks to scan for momentum opportunities.
Includes S&P 500, NASDAQ 100, and high-volume stocks.
"""

from typing import List, Set
import httpx
import pandas as pd

# S&P 500 symbols (top companies by market cap)
SP500_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH",
    "XOM", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV",
    "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD", "CSCO", "TMO", "ABT",
    "CRM", "ACN", "DHR", "NKE", "ADBE", "TXN", "NEE", "PM", "UPS", "MS",
    "RTX", "HON", "ORCL", "IBM", "QCOM", "LOW", "UNP", "SPGI", "INTU", "BA",
    "GE", "AMAT", "CAT", "DE", "AMD", "ISRG", "BKNG", "MDLZ", "ADP", "GILD",
    "SBUX", "ADI", "MMC", "LMT", "TJX", "VRTX", "SYK", "REGN", "CI", "CB",
    "BDX", "CVS", "MO", "SCHW", "DUK", "SO", "ZTS", "PLD", "BSX", "EQIX",
    "CME", "CL", "ITW", "NOC", "ICE", "SHW", "MU", "MCO", "PGR", "EOG",
    "WM", "HUM", "FDX", "EMR", "PSA", "SNPS", "ORLY", "GD", "CDNS", "APD",
]

# NASDAQ 100 tech-heavy symbols
NASDAQ100_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST",
    "PEP", "CSCO", "ADBE", "NFLX", "AMD", "CMCSA", "INTC", "INTU", "QCOM", "TXN",
    "HON", "AMGN", "AMAT", "BKNG", "ISRG", "SBUX", "ADI", "MDLZ", "GILD", "ADP",
    "VRTX", "REGN", "LRCX", "PYPL", "MU", "SNPS", "CDNS", "KLAC", "PANW", "MELI",
    "ORLY", "MAR", "ASML", "ABNB", "MNST", "CTAS", "FTNT", "KDP", "MCHP", "KHC",
    "AEP", "PAYX", "DXCM", "ADSK", "AZN", "EXC", "LULU", "CHTR", "CPRT", "PCAR",
    "MRVL", "ODFL", "NXPI", "ROST", "IDXX", "WDAY", "FAST", "CRWD", "VRSK", "GEHC",
    "CSGP", "BKR", "EA", "CTSH", "XEL", "FANG", "BIIB", "TEAM", "DLTR", "ANSS",
    "ZS", "ILMN", "DDOG", "WBD", "ALGN", "ENPH", "SIRI", "JD", "LCID", "RIVN",
    "COIN", "ROKU", "ZM", "DOCU", "PTON", "HOOD", "SOFI", "PLTR", "SNOW", "NET",
]

# High momentum/volatile stocks popular with traders
MOMENTUM_FAVORITES = [
    "NVDA", "AMD", "TSLA", "AAPL", "MSFT", "META", "GOOGL", "AMZN", "NFLX", "CRM",
    "COIN", "MARA", "RIOT", "MSTR", "PLTR", "SOFI", "HOOD", "RIVN", "LCID", "NIO",
    "SNOW", "NET", "CRWD", "DDOG", "ZS", "MDB", "PANW", "FTNT", "S", "OKTA",
    "SQ", "PYPL", "SHOP", "MELI", "SE", "BABA", "JD", "PDD", "GRAB", "CPNG",
    "ROKU", "TTD", "PINS", "SNAP", "SPOT", "RBLX", "U", "MTCH", "BMBL", "ABNB",
    "UBER", "LYFT", "DASH", "DKNG", "PENN", "MGM", "WYNN", "LVS", "CZR", "RCL",
    "CCL", "NCLH", "AAL", "UAL", "DAL", "LUV", "SAVE", "JBLU", "ALK", "HA",
    "GME", "AMC", "BB", "BBBY", "EXPR", "KOSS", "NAKD", "SNDL", "TLRY", "CGC",
    "SPY", "QQQ", "IWM", "DIA", "ARKK", "TQQQ", "SQQQ", "UVXY", "VXX", "SPXS",
]

# ETFs for sector momentum
SECTOR_ETFS = [
    "SPY", "QQQ", "IWM", "DIA",  # Major indices
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLU", "XLB", "XLRE", "XLC", "XLY",  # Sectors
    "ARKK", "ARKG", "ARKF", "ARKW", "ARKQ",  # Innovation
    "SMH", "SOXX", "XSD",  # Semiconductors
    "XBI", "IBB",  # Biotech
    "GLD", "SLV", "GDX",  # Precious metals
    "USO", "XOP",  # Oil
    "TLT", "HYG", "LQD",  # Bonds
]


def get_full_universe() -> List[str]:
    """Get the complete stock universe for scanning."""
    all_symbols: Set[str] = set()
    all_symbols.update(SP500_SYMBOLS)
    all_symbols.update(NASDAQ100_SYMBOLS)
    all_symbols.update(MOMENTUM_FAVORITES)
    # Remove any with dots (BRK.B etc) as they can cause issues
    all_symbols = {s for s in all_symbols if "." not in s}
    return sorted(list(all_symbols))


def get_quick_scan_universe() -> List[str]:
    """Get a smaller universe for quick scanning."""
    # Top 50 most liquid/traded stocks
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "CRM",
        "ORCL", "INTC", "CSCO", "ADBE", "PYPL", "SQ", "SHOP", "UBER", "ABNB", "COIN",
        "PLTR", "SOFI", "HOOD", "RIVN", "LCID", "NIO", "SNOW", "NET", "CRWD", "DDOG",
        "MDB", "PANW", "ZS", "OKTA", "ROKU", "SNAP", "PINS", "SPOT", "RBLX", "U",
        "SPY", "QQQ", "IWM", "ARKK", "XLK", "XLF", "XLE", "SMH", "GLD", "TLT",
    ]


def get_sector_etfs() -> List[str]:
    """Get sector ETFs for market breadth analysis."""
    return SECTOR_ETFS.copy()


async def fetch_sp500_symbols() -> List[str]:
    """Fetch current S&P 500 symbols from Wikipedia."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                timeout=10.0,
            )
            if response.status_code == 200:
                tables = pd.read_html(response.text)
                if tables:
                    df = tables[0]
                    if "Symbol" in df.columns:
                        symbols = df["Symbol"].tolist()
                        # Clean symbols
                        symbols = [s.replace(".", "-") for s in symbols if isinstance(s, str)]
                        return symbols
    except Exception:
        pass
    # Fallback to static list
    return SP500_SYMBOLS.copy()
