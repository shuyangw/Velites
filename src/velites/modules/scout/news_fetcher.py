"""
The News Aggregator - Business News Fetcher

Fetches business context to validate technical signals (The "Reality Check").
Sources: Tiingo, NewsData.io, and niche RSS feeds.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from velites.config import settings
from velites.logging import get_logger
from velites.modules.scout.exceptions import DataFetchError
from velites.modules.scout.models import NewsObject

logger = get_logger(__name__)


class BaseNewsFetcher(ABC):
    """Abstract base class for news fetching."""

    @abstractmethod
    async def fetch_news(
        self,
        tickers: list[str],
        keywords: list[str] | None = None,
        lookback_hours: int | None = None,
    ) -> list[NewsObject]:
        """Fetch news articles."""
        pass


class NewsFetcher(BaseNewsFetcher):
    """Fetches news from multiple sources."""

    SUPPLY_CHAIN_KEYWORDS = [
        "capacity",
        "yield",
        "shortage",
        "delay",
        "production",
        "manufacturing",
        "supply",
        "demand",
        "inventory",
        "backlog",
    ]

    def __init__(self) -> None:
        self.tiingo_api_key = settings.tiingo_api_key
        self.newsdata_api_key = settings.newsdata_api_key

    async def fetch_news(
        self,
        tickers: list[str],
        keywords: list[str] | None = None,
        lookback_hours: int = 24,
    ) -> list[NewsObject]:
        """
        Fetch news articles for given tickers.

        Args:
            tickers: Stock tickers to search for
            keywords: Additional keywords to prioritize
            lookback_hours: Hours to look back

        Returns:
            List of NewsObject instances

        Raises:
            DataFetchError: If fetching fails
        """
        keywords = keywords or self.SUPPLY_CHAIN_KEYWORDS
        cutoff_date = datetime.utcnow() - timedelta(hours=lookback_hours)

        logger.info(
            "fetching_news",
            tickers=tickers,
            keywords=keywords,
            lookback_hours=lookback_hours,
        )

        # TODO: Implement actual news API calls
        # - Tiingo News API
        # - NewsData.io API
        # - RSS feeds (AnandTech, Tom's Hardware, Semianalysis, DigiTimes)

        raise NotImplementedError("News fetcher not yet implemented")

    async def fetch_from_tiingo(
        self, tickers: list[str], start_date: datetime
    ) -> list[NewsObject]:
        """Fetch news from Tiingo API."""
        raise NotImplementedError()

    async def fetch_from_rss(self, feed_urls: list[str]) -> list[NewsObject]:
        """Fetch news from RSS feeds."""
        raise NotImplementedError()
