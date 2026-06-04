"""Tests for Market Fetcher."""

import pytest

from modules.scout.exceptions import DataFetchError
from modules.scout.market_fetcher import MarketFetcher
from modules.scout.models import LiquidityStatus


class TestMarketFetcher:
    """Tests for MarketFetcher class."""

    def test_classify_liquidity_high(self) -> None:
        """Test high liquidity classification."""
        fetcher = MarketFetcher()

        liquidity = fetcher._classify_liquidity(
            volume_30d_avg=5_000_000,
            spread_pct=0.1,
        )

        assert liquidity == LiquidityStatus.HIGH

    def test_classify_liquidity_medium(self) -> None:
        """Test medium liquidity classification."""
        fetcher = MarketFetcher()

        liquidity = fetcher._classify_liquidity(
            volume_30d_avg=800_000,
            spread_pct=0.8,
        )

        assert liquidity == LiquidityStatus.MEDIUM

    def test_classify_liquidity_low(self) -> None:
        """Test low liquidity classification."""
        fetcher = MarketFetcher()

        liquidity = fetcher._classify_liquidity(
            volume_30d_avg=300_000,
            spread_pct=1.5,
        )

        assert liquidity == LiquidityStatus.LOW

    def test_classify_liquidity_illiquid_low_volume(self) -> None:
        """Test illiquid classification due to low volume."""
        fetcher = MarketFetcher()

        liquidity = fetcher._classify_liquidity(
            volume_30d_avg=50_000,
            spread_pct=0.5,
        )

        assert liquidity == LiquidityStatus.ILLIQUID

    def test_classify_liquidity_illiquid_high_spread(self) -> None:
        """Test illiquid classification due to high spread."""
        fetcher = MarketFetcher()

        liquidity = fetcher._classify_liquidity(
            volume_30d_avg=1_000_000,
            spread_pct=2.5,
        )

        assert liquidity == LiquidityStatus.ILLIQUID

    def test_fetch_market_state_unknown_provider(self) -> None:
        """Test that unknown provider raises DataFetchError."""
        import asyncio

        fetcher = MarketFetcher()
        fetcher.provider = "unknown"

        with pytest.raises(DataFetchError, match="Unknown market data provider"):
            asyncio.new_event_loop().run_until_complete(fetcher.fetch_market_state("NVDA"))

    def test_fetch_from_alpaca_missing_keys(self) -> None:
        """Test that Alpaca fetcher raises DataFetchError if keys not configured."""
        import asyncio

        import config

        fetcher = MarketFetcher()

        # Temporarily clear the API keys
        original_key = config.settings.alpaca_api_key
        original_secret = config.settings.alpaca_secret_key
        config.settings.alpaca_api_key = ""
        config.settings.alpaca_secret_key = ""

        try:
            with pytest.raises(DataFetchError, match="(not configured|alpaca-py)"):
                asyncio.new_event_loop().run_until_complete(fetcher._fetch_from_alpaca("NVDA"))
        finally:
            config.settings.alpaca_api_key = original_key
            config.settings.alpaca_secret_key = original_secret

    def test_fetch_from_yfinance_requires_yfinance(self) -> None:
        """Test that yfinance fetcher raises DataFetchError if yfinance not installed."""
        import asyncio

        # Check if yfinance can be imported
        try:
            import yfinance  # noqa: F401

            pytest.skip("yfinance is installed, cannot test missing dependency")
        except ImportError:
            pass

        fetcher = MarketFetcher()

        with pytest.raises(DataFetchError, match="yfinance"):
            asyncio.new_event_loop().run_until_complete(fetcher._fetch_from_yfinance("NVDA"))

    def test_fetch_batch_market_state_empty_list(self) -> None:
        """Test batch fetch with empty ticker list."""
        import asyncio

        fetcher = MarketFetcher()

        results = asyncio.new_event_loop().run_until_complete(fetcher.fetch_batch_market_state([]))

        assert results == {}


class TestMarketFetcherWithMocks:
    """Tests using mocked yfinance responses."""

    def test_liquidity_thresholds(self) -> None:
        """Test boundary conditions for liquidity classification."""
        fetcher = MarketFetcher()

        # Boundary: exactly at HIGH threshold
        assert fetcher._classify_liquidity(1_000_000, 0.5) == LiquidityStatus.HIGH

        # Boundary: just below HIGH threshold (becomes MEDIUM)
        assert fetcher._classify_liquidity(999_999, 0.5) == LiquidityStatus.MEDIUM

        # Boundary: exactly at MEDIUM threshold
        assert fetcher._classify_liquidity(500_000, 1.0) == LiquidityStatus.MEDIUM

        # Boundary: just below MEDIUM threshold (becomes LOW)
        assert fetcher._classify_liquidity(499_999, 1.0) == LiquidityStatus.LOW
