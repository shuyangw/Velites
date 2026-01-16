"""
The Market Feeder - Market Data Fetcher

Provides current market state to prevent trading into illiquidity.
Sources: yfinance (Dev), Alpaca Data API (Prod).
"""

from abc import ABC, abstractmethod

from velites.config import settings
from velites.logging import get_logger
from velites.modules.scout.exceptions import DataFetchError
from velites.modules.scout.models import LiquidityStatus, MarketState

logger = get_logger(__name__)


class BaseMarketFetcher(ABC):
    """Abstract base class for market data fetching."""

    @abstractmethod
    async def fetch_market_state(self, ticker: str) -> MarketState:
        """Fetch current market state for a ticker."""
        pass

    @abstractmethod
    async def fetch_batch_market_state(self, tickers: list[str]) -> dict[str, MarketState]:
        """Fetch market state for multiple tickers."""
        pass


class MarketFetcher(BaseMarketFetcher):
    """Fetches market data from configured provider."""

    def __init__(self) -> None:
        self.provider = settings.market_data_provider

    async def fetch_market_state(self, ticker: str) -> MarketState:
        """
        Fetch current market state for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            MarketState instance

        Raises:
            DataFetchError: If fetching fails
        """
        logger.info("fetching_market_state", ticker=ticker, provider=self.provider)

        if self.provider == "yfinance":
            return await self._fetch_from_yfinance(ticker)
        elif self.provider == "alpaca":
            return await self._fetch_from_alpaca(ticker)
        else:
            raise DataFetchError(f"Unknown market data provider: {self.provider}")

    async def fetch_batch_market_state(self, tickers: list[str]) -> dict[str, MarketState]:
        """
        Fetch market state for multiple tickers.

        Args:
            tickers: List of stock ticker symbols

        Returns:
            Dict mapping ticker to MarketState
        """
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = await self.fetch_market_state(ticker)
            except DataFetchError as e:
                logger.warning("failed_to_fetch_ticker", ticker=ticker, error=str(e))
        return results

    async def _fetch_from_yfinance(self, ticker: str) -> MarketState:
        """Fetch from yfinance (development)."""
        # TODO: Implement yfinance fetching
        # import yfinance as yf
        # stock = yf.Ticker(ticker)
        raise NotImplementedError("yfinance fetcher not yet implemented")

    async def _fetch_from_alpaca(self, ticker: str) -> MarketState:
        """Fetch from Alpaca API (production)."""
        # TODO: Implement Alpaca API fetching
        raise NotImplementedError("Alpaca fetcher not yet implemented")

    def _classify_liquidity(
        self, volume_30d_avg: float, spread_pct: float
    ) -> LiquidityStatus:
        """Classify liquidity based on volume and spread."""
        if spread_pct > 2.0 or volume_30d_avg < 100_000:
            return LiquidityStatus.ILLIQUID
        elif spread_pct > 1.0 or volume_30d_avg < 500_000:
            return LiquidityStatus.LOW
        elif spread_pct > 0.5 or volume_30d_avg < 1_000_000:
            return LiquidityStatus.MEDIUM
        else:
            return LiquidityStatus.HIGH
