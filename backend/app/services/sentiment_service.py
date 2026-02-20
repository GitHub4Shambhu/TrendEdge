"""
TrendEdge Backend - Sentiment Analysis Service

Analyzes social media sentiment for stocks using FinBERT or similar models.
Combines data from multiple sources for comprehensive sentiment scoring.

AI Maintainability Notes:
- Modular source adapters for easy extension
- Clear sentiment score normalization (-1 to 1)
- Configurable weights for different sources
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings


class SentimentService:
    """
    Service for analyzing social sentiment around stocks.
    
    Combines sentiment from:
    - Twitter/X mentions
    - Reddit discussions (r/wallstreetbets, r/stocks, etc.)
    - News headlines
    - StockTwits
    
    All scores normalized to -1 (bearish) to +1 (bullish).
    """

    def __init__(self):
        self.settings = get_settings()
        self._cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._model = None  # Lazy load FinBERT

    def _load_model(self):
        """Lazy load the sentiment analysis model."""
        if self._model is None:
            try:
                from transformers import pipeline
                # Use FinBERT for financial sentiment
                self._model = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    device=-1,  # CPU
                )
            except Exception:
                # Fallback to basic sentiment
                self._model = "fallback"

    def _analyze_text(self, text: str) -> float:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score (-1 to 1)
        """
        self._load_model()

        if self._model == "fallback":
            # Simple keyword-based fallback
            positive_words = ["bull", "buy", "moon", "rocket", "gain", "profit", "up"]
            negative_words = ["bear", "sell", "crash", "loss", "down", "dump", "red"]
            
            text_lower = text.lower()
            pos_count = sum(1 for w in positive_words if w in text_lower)
            neg_count = sum(1 for w in negative_words if w in text_lower)
            
            total = pos_count + neg_count
            if total == 0:
                return 0.0
            return (pos_count - neg_count) / total

        # Use FinBERT
        try:
            result = self._model(text[:512])[0]  # Truncate to model limit
            label = result["label"].lower()
            score = result["score"]

            if label == "positive":
                return score
            elif label == "negative":
                return -score
            return 0.0
        except Exception:
            return 0.0

    async def get_sentiment_score(
        self,
        symbol: str,
        texts: Optional[List[str]] = None,
    ) -> float:
        """
        Get aggregated sentiment score for a symbol.
        
        Args:
            symbol: Ticker symbol
            texts: Optional list of texts to analyze (for testing)
            
        Returns:
            Aggregated sentiment score (-1 to 1)
        """
        # Check cache
        if symbol in self._cache:
            cached_score, cached_time = self._cache[symbol]
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return cached_score

        if texts is None:
            # In production, would fetch from APIs
            # For now, return neutral
            return 0.0

        # Analyze all texts
        scores = [self._analyze_text(text) for text in texts]

        if not scores:
            return 0.0

        # Weighted average (more recent = higher weight)
        weights = [1.0 + (i * 0.1) for i in range(len(scores))]
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        total_weight = sum(weights)
        
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Cache result
        self._cache[symbol] = (final_score, datetime.utcnow())

        return round(final_score, 4)

    async def get_market_sentiment(self) -> float:
        """
        Get overall market sentiment based on major indices.
        
        Returns:
            Market sentiment score (-1 to 1)
        """
        # Simplified: would aggregate from SPY, QQQ, etc.
        # For now, return neutral
        return 0.0


# Singleton instance
_sentiment_service: Optional[SentimentService] = None


def get_sentiment_service() -> SentimentService:
    """Get or create the sentiment service singleton."""
    global _sentiment_service
    if _sentiment_service is None:
        _sentiment_service = SentimentService()
    return _sentiment_service
