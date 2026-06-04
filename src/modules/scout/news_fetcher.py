"""
The News Aggregator - Business News Fetcher

Fetches business context to validate technical signals (The "Reality Check").
Sources: Tiingo, NewsData.io, and niche RSS feeds.
"""

import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

import httpx

from config import settings
from logging_config import get_logger
from modules.scout.exceptions import DataFetchError
from modules.scout.models import NewsObject

logger = get_logger(__name__)

# Tiingo API configuration
TIINGO_NEWS_URL = "https://api.tiingo.com/iex"


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
        use_tiingo: bool = True,
    ) -> list[NewsObject]:
        """
        Fetch news articles for given tickers.

        Args:
            tickers: Stock tickers to search for
            keywords: Additional keywords to prioritize
            lookback_hours: Hours to look back
            use_tiingo: Whether to use Tiingo API (if available)

        Returns:
            List of NewsObject instances

        Raises:
            DataFetchError: If fetching fails
        """
        keywords = keywords or self.SUPPLY_CHAIN_KEYWORDS
        cutoff_date = datetime.now(UTC) - timedelta(hours=lookback_hours)

        logger.info(
            "fetching_news",
            tickers=tickers,
            keywords=keywords,
            lookback_hours=lookback_hours,
        )

        all_news: list[NewsObject] = []

        # Try Tiingo first if API key is available and enabled
        if use_tiingo and self.tiingo_api_key and tickers:
            try:
                tiingo_news = await self.fetch_from_tiingo(tickers, cutoff_date)
                all_news.extend(tiingo_news)
                logger.info("tiingo_source_added", count=len(tiingo_news))
            except DataFetchError as e:
                logger.warning("tiingo_fetch_failed", error=str(e))

        # Always fetch from RSS feeds as fallback/supplement
        rss_news = await self.fetch_from_rss()
        all_news.extend(rss_news)

        # Filter by cutoff date (handle both timezone-aware and naive timestamps)
        filtered_news = []
        for n in all_news:
            news_time = n.timestamp
            if news_time.tzinfo is None:
                news_time = news_time.replace(tzinfo=UTC)
            if news_time >= cutoff_date:
                filtered_news.append(n)

        # Filter by keywords if specified
        if keywords:
            keyword_filtered = []
            for news in filtered_news:
                text = f"{news.headline} {news.summary}".lower()
                if any(kw.lower() in text for kw in keywords):
                    # Add matched keywords
                    matched = [kw for kw in keywords if kw.lower() in text]
                    news.keywords = matched
                    keyword_filtered.append(news)
            filtered_news = keyword_filtered

        # Filter by tickers if specified
        if tickers:
            ticker_filtered = []
            for news in filtered_news:
                text = f"{news.headline} {news.summary}".upper()
                matched_tickers = [t for t in tickers if t in text]
                if matched_tickers:
                    news.tickers = matched_tickers
                    ticker_filtered.append(news)
            # If tickers specified, only return news mentioning those tickers
            if ticker_filtered:
                filtered_news = ticker_filtered

        logger.info(
            "news_fetched",
            total_from_rss=len(all_news),
            after_filters=len(filtered_news),
        )

        return filtered_news

    async def fetch_from_tiingo(self, tickers: list[str], start_date: datetime) -> list[NewsObject]:
        """
        Fetch news from Tiingo API.

        Args:
            tickers: List of stock tickers to search for
            start_date: Only return news after this date

        Returns:
            List of NewsObject instances

        Raises:
            DataFetchError: If API call fails
        """
        if not self.tiingo_api_key:
            raise DataFetchError("Tiingo API key not configured")

        news_items: list[NewsObject] = []

        # Format start date for Tiingo API (YYYY-MM-DD)
        start_str = start_date.strftime("%Y-%m-%d")

        # Tiingo news endpoint
        url = "https://api.tiingo.com/tiingo/news"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.tiingo_api_key}",
        }

        # Build query parameters
        params = {
            "tickers": ",".join(tickers),
            "startDate": start_str,
            "limit": 50,  # Reasonable limit per request
            "sortBy": "publishedDate",
        }

        logger.info(
            "fetching_tiingo_news",
            tickers=tickers,
            start_date=start_str,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 401:
                    raise DataFetchError("Tiingo API authentication failed - check API key")
                elif response.status_code == 429:
                    raise DataFetchError("Tiingo API rate limit exceeded")
                elif response.status_code != 200:
                    raise DataFetchError(f"Tiingo API error: {response.status_code}")

                data = response.json()

                for article in data:
                    # Parse publication date
                    pub_date_str = article.get("publishedDate", "")
                    if pub_date_str:
                        # Tiingo returns ISO format with timezone
                        try:
                            timestamp = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                        except ValueError:
                            timestamp = datetime.now(UTC)
                    else:
                        timestamp = datetime.now(UTC)

                    # Extract tickers mentioned in the article
                    article_tickers = article.get("tickers", [])

                    # Get description/summary
                    description = article.get("description", "")
                    if description:
                        # Clean up and truncate
                        description = re.sub(r"<[^>]+>", "", description)[:500]

                    # Generate unique ID
                    article_id = article.get("id", "")
                    news_id = (
                        f"tiingo_{article_id}"
                        if article_id
                        else f"tiingo_{hash(article.get('url', '')) & 0xFFFFFFFF:08x}"
                    )

                    news = NewsObject(
                        id=news_id,
                        headline=article.get("title", "No Title").strip(),
                        summary=description.strip(),
                        source=article.get("source", "Tiingo"),
                        url=article.get("url", ""),
                        timestamp=timestamp,
                        tickers=article_tickers,
                        keywords=[],  # Will be populated by filtering logic
                    )
                    news_items.append(news)

                logger.info(
                    "tiingo_news_fetched",
                    count=len(news_items),
                    tickers=tickers,
                )

        except httpx.TimeoutException:
            raise DataFetchError("Tiingo API request timed out")
        except httpx.RequestError as e:
            raise DataFetchError(f"Tiingo API connection error: {e}")
        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Failed to fetch Tiingo news: {e}")

        return news_items

    async def fetch_from_rss(self, feed_urls: list[str] | None = None) -> list[NewsObject]:
        """
        Fetch news from RSS feeds.

        Args:
            feed_urls: Optional list of RSS feed URLs. Uses defaults if not specified.

        Returns:
            List of NewsObject instances
        """
        try:
            import feedparser
        except ImportError:
            raise DataFetchError("feedparser is required: pip install feedparser")

        # Default semiconductor/tech RSS feeds
        default_feeds = [
            "https://semianalysis.com/feed/",
            "https://www.anandtech.com/rss/",
            "https://www.tomshardware.com/feeds/all",
            "https://techcrunch.com/feed/",
        ]

        feeds_to_fetch = feed_urls or default_feeds
        news_items: list[NewsObject] = []

        for feed_url in feeds_to_fetch:
            try:
                logger.debug("fetching_rss_feed", url=feed_url)
                feed = feedparser.parse(feed_url)

                # Get feed title for source attribution
                feed_title = feed.feed.get("title", "RSS Feed")

                for entry in feed.entries[:15]:  # Limit per feed
                    # Parse publication date
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        timestamp = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        timestamp = datetime(*entry.updated_parsed[:6])
                    else:
                        timestamp = datetime.utcnow()

                    # Get summary/description
                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = entry.summary
                    elif hasattr(entry, "description"):
                        summary = entry.description

                    # Clean up HTML tags from summary
                    summary = re.sub(r"<[^>]+>", "", summary)[:500]

                    # Generate unique ID from link
                    news_id = f"rss_{hash(entry.link) & 0xFFFFFFFF:08x}"

                    news = NewsObject(
                        id=news_id,
                        headline=entry.title.strip() if hasattr(entry, "title") else "No Title",
                        summary=summary.strip(),
                        source=feed_title,
                        url=entry.link if hasattr(entry, "link") else "",
                        timestamp=timestamp,
                        tickers=[],
                        keywords=[],
                    )
                    news_items.append(news)

            except Exception as e:
                logger.warning("rss_fetch_failed", feed=feed_url, error=str(e))
                continue

        logger.info(
            "rss_feeds_fetched", total_items=len(news_items), feeds_processed=len(feeds_to_fetch)
        )
        return news_items
