"""
TrendEdge Backend - Core Configuration

This module provides centralized configuration management using Pydantic Settings.
All environment variables are validated and typed for AI-maintainability.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: str = "development"
    debug: bool = True

    # API Keys
    alpha_vantage_api_key: str = ""
    polygon_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/trendedge"
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    # Momentum Algorithm Settings
    momentum_lookback_days: int = 20
    momentum_threshold: float = 0.02
    sentiment_weight: float = 0.3

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
