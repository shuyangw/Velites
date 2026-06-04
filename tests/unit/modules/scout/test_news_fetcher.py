"""Tests for News Fetcher."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.scout.exceptions import DataFetchError
from modules.scout.models import NewsObject
from modules.scout.news_fetcher import NewsFetcher


class TestNewsFetcher:
    """Tests for NewsFetcher class."""

    def test_supply_chain_keywords(self) -> None:
        """Test that supply chain keywords are defined."""
        fetcher = NewsFetcher()

        assert len(fetcher.SUPPLY_CHAIN_KEYWORDS) > 0
        assert "shortage" in fetcher.SUPPLY_CHAIN_KEYWORDS
        assert "capacity" in fetcher.SUPPLY_CHAIN_KEYWORDS
        assert "yield" in fetcher.SUPPLY_CHAIN_KEYWORDS

    def test_init_loads_settings(self) -> None:
        """Test that NewsFetcher loads API keys from settings."""
        fetcher = NewsFetcher()

        # API keys should be set (may be None if not configured)
        assert hasattr(fetcher, "tiingo_api_key")
        assert hasattr(fetcher, "newsdata_api_key")

    def test_fetch_from_tiingo_missing_key(self) -> None:
        """Test that Tiingo fetcher raises DataFetchError if key not configured."""
        import asyncio

        import config

        fetcher = NewsFetcher()

        # Temporarily clear the API key
        original_key = config.settings.tiingo_api_key
        config.settings.tiingo_api_key = ""
        fetcher.tiingo_api_key = ""

        try:
            with pytest.raises(DataFetchError, match="not configured"):
                asyncio.new_event_loop().run_until_complete(
                    fetcher.fetch_from_tiingo(["NVDA"], datetime.now(UTC))
                )
        finally:
            config.settings.tiingo_api_key = original_key
            fetcher.tiingo_api_key = original_key

    @pytest.mark.skip(reason="feedparser is installed, cannot test missing dependency")
    def test_fetch_from_rss_requires_feedparser(self) -> None:
        """Test that RSS fetcher raises DataFetchError if feedparser not installed."""
        import asyncio

        fetcher = NewsFetcher()

        with pytest.raises(DataFetchError, match="feedparser"):
            asyncio.new_event_loop().run_until_complete(fetcher.fetch_from_rss())


class TestNewsFiltering:
    """Tests for news filtering logic."""

    @pytest.fixture
    def sample_news_items(self) -> list[NewsObject]:
        """Create sample news items for testing."""
        return [
            NewsObject(
                id="news_1",
                headline="NVDA Reports Record Revenue Amid GPU Shortage",
                summary="NVIDIA corporation reported strong revenue growth driven by AI demand...",
                source="Test Feed",
                url="https://example.com/1",
                timestamp=datetime.utcnow() - timedelta(hours=2),
                tickers=[],
                keywords=[],
            ),
            NewsObject(
                id="news_2",
                headline="Tech Stocks Rally on Fed Decision",
                summary="Technology stocks moved higher following Federal Reserve announcement...",
                source="Test Feed",
                url="https://example.com/2",
                timestamp=datetime.utcnow() - timedelta(hours=12),
                tickers=[],
                keywords=[],
            ),
            NewsObject(
                id="news_3",
                headline="TSM Increases Production Capacity",
                summary="Taiwan Semiconductor plans to expand manufacturing capacity to meet demand...",
                source="Test Feed",
                url="https://example.com/3",
                timestamp=datetime.utcnow() - timedelta(hours=6),
                tickers=[],
                keywords=[],
            ),
            NewsObject(
                id="news_4",
                headline="Old News About Weather",
                summary="The weather was nice yesterday...",
                source="Test Feed",
                url="https://example.com/4",
                timestamp=datetime.utcnow() - timedelta(days=5),
                tickers=[],
                keywords=[],
            ),
        ]

    def test_keyword_matching_in_headline(self, sample_news_items: list[NewsObject]) -> None:
        """Test that keywords are matched in headlines."""
        news = sample_news_items[0]  # Contains "Shortage"
        text = f"{news.headline} {news.summary}".lower()

        keywords = ["shortage", "delay"]
        matched = [kw for kw in keywords if kw.lower() in text]

        assert "shortage" in matched
        assert "delay" not in matched

    def test_keyword_matching_in_summary(self, sample_news_items: list[NewsObject]) -> None:
        """Test that keywords are matched in summary."""
        news = sample_news_items[2]  # Contains "capacity" in summary
        text = f"{news.headline} {news.summary}".lower()

        keywords = ["capacity", "production"]
        matched = [kw for kw in keywords if kw.lower() in text]

        assert "capacity" in matched
        assert "production" in matched

    def test_ticker_matching(self, sample_news_items: list[NewsObject]) -> None:
        """Test ticker matching in headlines."""
        news = sample_news_items[0]  # Contains "NVDA" in headline
        text = f"{news.headline} {news.summary}".upper()

        tickers = ["NVDA", "AMD", "INTC"]
        matched = [t for t in tickers if t in text]

        assert "NVDA" in matched
        assert "AMD" not in matched

    def test_cutoff_date_filtering(self, sample_news_items: list[NewsObject]) -> None:
        """Test filtering by cutoff date."""
        cutoff = datetime.utcnow() - timedelta(hours=24)

        filtered = [n for n in sample_news_items if n.timestamp >= cutoff]

        # Should include items from last 24 hours
        assert len(filtered) == 3
        # Should exclude old news (5 days old)
        assert all(n.id != "news_4" for n in filtered)


class TestNewsObjectCreation:
    """Tests for NewsObject model."""

    def test_news_object_fields(self) -> None:
        """Test NewsObject required fields."""
        news = NewsObject(
            id="test_123",
            headline="Test Headline",
            summary="Test Summary",
            source="Test Source",
            url="https://example.com",
            timestamp=datetime.utcnow(),
            tickers=["NVDA", "AMD"],
            keywords=["shortage", "demand"],
        )

        assert news.id == "test_123"
        assert news.headline == "Test Headline"
        assert "NVDA" in news.tickers
        assert "shortage" in news.keywords

    def test_news_object_default_empty_lists(self) -> None:
        """Test NewsObject with empty tickers and keywords."""
        news = NewsObject(
            id="test_456",
            headline="Test",
            summary="Test",
            source="Test",
            url="https://example.com",
            timestamp=datetime.utcnow(),
            tickers=[],
            keywords=[],
        )

        assert news.tickers == []
        assert news.keywords == []
