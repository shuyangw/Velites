"""Configuration management using Pydantic settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Velites"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Data paths
    data_dir: str = "data"
    knowledge_graph_path: str = "data/knowledge_graph_v1_2.json"
    watchlist_path: str = "data/watchlist.json"

    # Scout - ArXiv
    arxiv_categories: list[str] = Field(default=["cs.AI", "cs.LG", "cs.AR", "cs.CV"])
    arxiv_max_results: int = 100
    arxiv_lookback_hours: int = 72  # 72h accounts for weekends + batch publishing

    # Scout - News
    tiingo_api_key: str = ""
    newsdata_api_key: str = ""

    # Scout - Market Data
    market_data_provider: Literal["yfinance", "alpaca"] = "yfinance"
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # Analyst - LLM
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1

    # Analyst - Sentiment
    sentiment_model: str = "ProsusAI/finbert"
    sentiment_veto_threshold: float = -0.6

    # Analyst - Confluence Thresholds
    confluence_innovation_threshold: float = 0.7
    confluence_sentiment_veto_threshold: float = -0.5
    confluence_hype_threshold: float = 3.0

    # Courier - Homeguard
    homeguard_webhook_url: str = ""
    homeguard_output_dir: str = "output/signals"

    # Courier - Liquidity Guards
    max_spread_pct: float = 2.0
    min_volume_usd: float = 500_000.0

    # Scribe - Database
    database_url: str = "sqlite:///data/velites.db"

    # Scheduling
    run_mode: Literal["single", "scheduled"] = "single"
    run_interval_hours: int = 4
    run_at_startup: bool = True

    # Logging
    log_file_path: str = "logs/velites.log"
    log_to_file: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
