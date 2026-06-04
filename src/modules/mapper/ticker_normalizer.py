"""
The Ticker Normalizer - US Exchange Normalization

Ensures tradeability on US exchanges (Alpaca/IBKR) by converting
international tickers to US ADRs and flagging liquidity risks.

Based on the v1.2 knowledge graph structure:
- ticker_normalization.mappings: Non-US ticker -> US ADR mappings
- ticker_normalization.trading_flags.tradeable_us: List of tradeable US tickers
- ticker_normalization.trading_flags.track_only: List of track-only (non-tradeable) tickers
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from logging_config import get_logger
from modules.mapper.models import RiskFlag, TradeableTicker

if TYPE_CHECKING:
    from modules.mapper.graph_engine import GraphEngine

logger = get_logger(__name__)

# Non-US exchange suffixes
NON_US_SUFFIXES = [".KS", ".T", ".TW", ".DE", ".HK", ".L", ".PA", ".F"]

# Known US exchanges
US_EXCHANGES = {
    "NYSE": ["BRK", "JPM", "JNJ", "V", "PG", "UNH", "HD", "MA"],
    "NASDAQ": [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        "AMD",
        "INTC",
        "QCOM",
        "AVGO",
        "ASML",
    ],
    "OTC": ["SSNLF", "NTDOY", "SKHIY", "TOELY", "PCRFY", "AJINY", "MDTKF", "HNHPF"],
}

# Default venue for US tickers
DEFAULT_VENUE = "NASDAQ"


class TickerNormalizer:
    """
    Normalizes tickers to US-tradeable symbols.

    Converts international tickers to US ADRs and applies risk flags
    based on liquidity characteristics.

    Usage:
        >>> normalizer = TickerNormalizer(graph_engine)
        >>> result = normalizer.normalize("005930.KS")
        >>> print(result.symbol)  # "SSNLF"
        >>> print(result.is_adr)  # True
    """

    def __init__(self, graph_engine: GraphEngine) -> None:
        """
        Initialize the ticker normalizer.

        Args:
            graph_engine: Loaded GraphEngine instance
        """
        self.graph_engine = graph_engine
        self._mappings: dict[str, dict] = {}
        self._tradeable_us: set[str] = set()
        self._track_only: set[str] = set()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Ensure normalization data is loaded."""
        if self._loaded:
            return

        graph_data = self.graph_engine.graph_data
        norm_data = graph_data.get("ticker_normalization", {})

        self._mappings = norm_data.get("mappings", {})
        trading_flags = norm_data.get("trading_flags", {})
        self._tradeable_us = set(trading_flags.get("tradeable_us", []))
        self._track_only = set(trading_flags.get("track_only", []))

        self._loaded = True

        logger.info(
            "ticker_normalization_loaded",
            mappings=len(self._mappings),
            tradeable=len(self._tradeable_us),
            track_only=len(self._track_only),
        )

    def normalize(self, ticker: str) -> TradeableTicker:
        """
        Normalize a ticker to US-tradeable symbol.

        Args:
            ticker: Original ticker (may be international, e.g., "005930.KS")

        Returns:
            TradeableTicker with US symbol and risk flags

        Example:
            >>> normalizer.normalize("005930.KS")
            TradeableTicker(
                symbol="SSNLF",
                original_symbol="005930.KS",
                venue="OTC",
                is_adr=True,
                risk_flags=[RiskFlag.LIMIT_ORDER_ONLY, RiskFlag.LOW_LIQUIDITY]
            )
        """
        self._ensure_loaded()

        logger.debug("normalizing_ticker", original=ticker)

        # Check if it's already a US ticker (no foreign suffix)
        if self._is_us_ticker(ticker):
            return self._normalize_us_ticker(ticker)

        # Look up in mappings for non-US tickers
        if ticker in self._mappings:
            mapping = self._mappings[ticker]
            return self._create_from_mapping(ticker, mapping)

        # Check if this is a US ADR that has a native ticker mapping
        # (e.g., TOELY has native 8035.T)
        for us_ticker, mapping in self._mappings.items():
            if mapping.get("native") == ticker:
                return self._normalize_us_ticker(us_ticker)

        # Unknown non-US ticker - mark as not tradeable
        logger.warning("unknown_non_us_ticker", ticker=ticker)
        return TradeableTicker(
            symbol=ticker,
            original_symbol=ticker,
            venue="UNKNOWN",
            is_adr=False,
            risk_flags=[RiskFlag.LOW_LIQUIDITY],
        )

    def _is_us_ticker(self, ticker: str) -> bool:
        """Check if ticker is a US exchange ticker."""
        return not any(suffix in ticker for suffix in NON_US_SUFFIXES)

    def _normalize_us_ticker(self, ticker: str) -> TradeableTicker:
        """Normalize a ticker that's already US-listed."""
        self._ensure_loaded()

        risk_flags: list[RiskFlag] = []

        # Check if it's track-only
        if ticker in self._track_only:
            risk_flags.append(RiskFlag.LOW_LIQUIDITY)

        # Check if it's OTC (typically thin liquidity)
        if ticker in US_EXCHANGES.get("OTC", []) or ticker in self._tradeable_us:
            # OTC stocks should use limit orders
            if self._get_liquidity(ticker) in ("low", "very_low"):
                risk_flags.append(RiskFlag.LIMIT_ORDER_ONLY)
                risk_flags.append(RiskFlag.LOW_LIQUIDITY)

        venue = self._get_venue_for_ticker(ticker)

        return TradeableTicker(
            symbol=ticker,
            original_symbol=None,
            venue=venue,
            is_adr=ticker in self._tradeable_us,
            risk_flags=risk_flags,
        )

    def _create_from_mapping(self, original: str, mapping: dict) -> TradeableTicker:
        """Create TradeableTicker from a normalization mapping entry."""
        us_adr = mapping.get("us_adr")
        liquidity = mapping.get("us_liquidity", "medium")

        risk_flags: list[RiskFlag] = []

        # Apply liquidity-based risk flags
        if liquidity == "low":
            risk_flags.append(RiskFlag.LOW_LIQUIDITY)
            risk_flags.append(RiskFlag.LIMIT_ORDER_ONLY)
        elif liquidity == "very_low":
            risk_flags.append(RiskFlag.LOW_LIQUIDITY)
            risk_flags.append(RiskFlag.LIMIT_ORDER_ONLY)
            risk_flags.append(RiskFlag.OTC)

        # Check if track-only
        if us_adr and us_adr in self._track_only:
            risk_flags.append(RiskFlag.LOW_LIQUIDITY)

        venue = (
            "OTC"
            if liquidity in ("low", "very_low")
            else self._get_venue_for_ticker(us_adr or original)
        )

        return TradeableTicker(
            symbol=us_adr or original,
            original_symbol=original,
            venue=venue,
            is_adr=us_adr is not None,
            risk_flags=risk_flags,
        )

    def _get_liquidity(self, ticker: str) -> str:
        """Get liquidity classification for a ticker."""
        self._ensure_loaded()

        # Check mappings
        for mapping in self._mappings.values():
            if mapping.get("us_adr") == ticker:
                return mapping.get("us_liquidity", "medium")

        # Default based on exchange
        if ticker in US_EXCHANGES.get("OTC", []):
            return "low"

        return "high"

    def _get_venue_for_ticker(self, ticker: str) -> str:
        """Determine trading venue for a ticker."""
        for venue, tickers in US_EXCHANGES.items():
            if ticker in tickers:
                return venue
        return DEFAULT_VENUE

    def is_tradeable(self, ticker: str) -> bool:
        """
        Check if a ticker is tradeable on US exchanges.

        Args:
            ticker: Ticker to check

        Returns:
            True if tradeable, False otherwise
        """
        self._ensure_loaded()

        # Track-only tickers are not tradeable
        if ticker in self._track_only:
            return False

        # US tickers are generally tradeable
        if self._is_us_ticker(ticker):
            return True

        # Check if there's a US ADR
        if ticker in self._mappings:
            mapping = self._mappings[ticker]
            us_adr = mapping.get("us_adr")
            # Has ADR and it's not track-only
            return us_adr is not None and us_adr not in self._track_only

        return False

    def get_us_ticker(self, ticker: str) -> str | None:
        """
        Convert any ticker to US-tradeable equivalent.

        Args:
            ticker: Original ticker

        Returns:
            US-tradeable ticker symbol or None if not tradeable

        Example:
            >>> normalizer.get_us_ticker("005930.KS")
            "SSNLF"
            >>> normalizer.get_us_ticker("NVDA")
            "NVDA"
            >>> normalizer.get_us_ticker("MDTKF")  # track-only
            None
        """
        self._ensure_loaded()

        # Already US and tradeable
        if self._is_us_ticker(ticker) and ticker not in self._track_only:
            return ticker

        # Look up ADR
        if ticker in self._mappings:
            mapping = self._mappings[ticker]
            us_adr = mapping.get("us_adr")
            if us_adr and us_adr not in self._track_only:
                return us_adr

        return None

    def get_venue(self, ticker: str) -> str:
        """
        Get the trading venue for a ticker.

        Args:
            ticker: Ticker to look up

        Returns:
            Venue string (e.g., "NASDAQ", "NYSE", "OTC")
        """
        normalized = self.normalize(ticker)
        return normalized.venue

    def get_all_track_only(self) -> set[str]:
        """Get set of all track-only (non-tradeable) tickers."""
        self._ensure_loaded()
        return self._track_only.copy()

    def get_all_tradeable_adrs(self) -> set[str]:
        """Get set of all tradeable US ADRs."""
        self._ensure_loaded()
        return self._tradeable_us.copy()

    def should_use_limit_order(self, ticker: str) -> bool:
        """
        Check if a ticker should only use limit orders (thin liquidity).

        Args:
            ticker: Ticker to check

        Returns:
            True if limit orders recommended, False otherwise
        """
        normalized = self.normalize(ticker)
        return RiskFlag.LIMIT_ORDER_ONLY in normalized.risk_flags
