"""
The Market Feeder - Market Data Fetcher

Provides current market state to prevent trading into illiquidity.
Sources: yfinance (Dev), Alpaca Data API (Prod).
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from config import settings
from logging_config import get_logger
from modules.scout.exceptions import DataFetchError
from modules.scout.models import LiquidityStatus, MarketState

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
        try:
            import yfinance as yf
        except ImportError:
            raise DataFetchError("yfinance is required: pip install yfinance")

        try:
            stock = yf.Ticker(ticker)

            # Get historical data for 30-day average volume
            hist = stock.history(period="1mo")

            if hist.empty:
                raise DataFetchError(f"No data available for ticker: {ticker}")

            # Get the latest bar
            latest = hist.iloc[-1]

            # Calculate 30-day average volume
            avg_volume = float(hist["Volume"].mean())

            # Get quote info for bid/ask spread
            info = stock.info

            # Estimate spread from bid/ask if available
            bid = info.get("bid", 0) or latest["Close"] * 0.999
            ask = info.get("ask", 0) or latest["Close"] * 1.001

            # Calculate spread percentage
            mid_price = (bid + ask) / 2 if bid and ask else latest["Close"]
            spread_pct = ((ask - bid) / mid_price) * 100 if bid and ask and mid_price > 0 else 0.1

            # Classify liquidity
            liquidity = self._classify_liquidity(avg_volume, spread_pct)

            return MarketState(
                ticker=ticker,
                price=float(latest["Close"]),
                volume_30d_avg=avg_volume,
                spread_pct=spread_pct,
                liquidity_status=liquidity,
                open=float(latest["Open"]),
                high=float(latest["High"]),
                low=float(latest["Low"]),
                close=float(latest["Close"]),
                volume=int(latest["Volume"]),
            )

        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Failed to fetch market data for {ticker}: {e}")

    async def _fetch_from_alpaca(self, ticker: str) -> MarketState:
        """Fetch from Alpaca API (production)."""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
            from alpaca.data.timeframe import TimeFrame
        except ImportError:
            raise DataFetchError("alpaca-py is required: pip install alpaca-py")

        if not settings.alpaca_api_key or not settings.alpaca_secret_key:
            raise DataFetchError("Alpaca API keys not configured")

        try:
            # Create Alpaca data client
            client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )

            # Get latest quote for current price and spread
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=ticker)
            quote_response = client.get_stock_latest_quote(quote_request)
            quote = quote_response[ticker]

            # Get 30-day bars for volume average
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=30)

            bars_request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
            )
            bars_response = client.get_stock_bars(bars_request)
            bars = bars_response[ticker]

            if not bars:
                raise DataFetchError(f"No historical data available for ticker: {ticker}")

            # Calculate 30-day average volume
            volumes = [bar.volume for bar in bars]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0

            # Get latest bar for OHLCV
            latest_bar = bars[-1]

            # Calculate spread percentage from bid/ask
            bid_price = (
                float(quote.bid_price) if quote.bid_price else float(latest_bar.close) * 0.999
            )
            ask_price = (
                float(quote.ask_price) if quote.ask_price else float(latest_bar.close) * 1.001
            )
            mid_price = (
                (bid_price + ask_price) / 2 if bid_price and ask_price else float(latest_bar.close)
            )
            spread_pct = ((ask_price - bid_price) / mid_price) * 100 if mid_price > 0 else 0.1

            # Classify liquidity
            liquidity = self._classify_liquidity(avg_volume, spread_pct)

            return MarketState(
                ticker=ticker,
                price=float(latest_bar.close),
                volume_30d_avg=avg_volume,
                spread_pct=spread_pct,
                liquidity_status=liquidity,
                open=float(latest_bar.open),
                high=float(latest_bar.high),
                low=float(latest_bar.low),
                close=float(latest_bar.close),
                volume=int(latest_bar.volume),
            )

        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Alpaca API error for {ticker}: {e}")

    def _classify_liquidity(self, volume_30d_avg: float, spread_pct: float) -> LiquidityStatus:
        """Classify liquidity based on volume and spread."""
        if spread_pct > 2.0 or volume_30d_avg < 100_000:
            return LiquidityStatus.ILLIQUID
        elif spread_pct > 1.0 or volume_30d_avg < 500_000:
            return LiquidityStatus.LOW
        elif spread_pct > 0.5 or volume_30d_avg < 1_000_000:
            return LiquidityStatus.MEDIUM
        else:
            return LiquidityStatus.HIGH
