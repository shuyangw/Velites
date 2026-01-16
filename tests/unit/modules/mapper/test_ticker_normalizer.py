"""Tests for Ticker Normalizer."""

import pytest

from velites.modules.mapper.graph_engine import GraphEngine
from velites.modules.mapper.ticker_normalizer import TickerNormalizer
from velites.modules.mapper.models import RiskFlag


class TestTickerNormalizerWithRealData:
    """Tests using the actual knowledge graph file."""

    @pytest.fixture
    def normalizer(self) -> TickerNormalizer:
        """Create normalizer with real knowledge graph."""
        engine = GraphEngine("data/knowledge_graph_v1_2.json")
        engine.load_graph()
        return TickerNormalizer(engine)

    def test_normalize_us_ticker(self, normalizer: TickerNormalizer) -> None:
        """Test normalizing a US ticker (passthrough)."""
        result = normalizer.normalize("NVDA")

        assert result.symbol == "NVDA"
        assert result.original_symbol is None
        assert result.is_adr is False

    def test_normalize_korean_ticker_samsung(self, normalizer: TickerNormalizer) -> None:
        """Test normalizing Samsung (Korean ticker to US ADR)."""
        result = normalizer.normalize("005930.KS")

        assert result.symbol == "SSNLF"
        assert result.original_symbol == "005930.KS"
        assert result.is_adr is True
        # Samsung ADR has low liquidity
        assert RiskFlag.LOW_LIQUIDITY in result.risk_flags

    def test_normalize_sk_hynix(self, normalizer: TickerNormalizer) -> None:
        """Test normalizing SK Hynix."""
        result = normalizer.normalize("000660.KS")

        assert result.symbol == "SKHIY"
        assert result.original_symbol == "000660.KS"
        assert result.is_adr is True

    def test_is_tradeable_us_ticker(self, normalizer: TickerNormalizer) -> None:
        """Test tradeability for US tickers."""
        assert normalizer.is_tradeable("NVDA") is True
        assert normalizer.is_tradeable("ASML") is True
        assert normalizer.is_tradeable("TSM") is True

    def test_is_tradeable_track_only(self, normalizer: TickerNormalizer) -> None:
        """Test tradeability for track-only tickers."""
        # MDTKF (MediaTek) and HNHPF (Foxconn) are track-only
        assert normalizer.is_tradeable("MDTKF") is False
        assert normalizer.is_tradeable("HNHPF") is False

    def test_is_tradeable_non_us_with_adr(self, normalizer: TickerNormalizer) -> None:
        """Test tradeability for non-US tickers with ADRs."""
        # Samsung has ADR
        assert normalizer.is_tradeable("005930.KS") is True

    def test_get_us_ticker_passthrough(self, normalizer: TickerNormalizer) -> None:
        """Test get_us_ticker for US tickers."""
        assert normalizer.get_us_ticker("NVDA") == "NVDA"
        assert normalizer.get_us_ticker("AMD") == "AMD"

    def test_get_us_ticker_conversion(self, normalizer: TickerNormalizer) -> None:
        """Test get_us_ticker for non-US tickers."""
        assert normalizer.get_us_ticker("005930.KS") == "SSNLF"
        assert normalizer.get_us_ticker("000660.KS") == "SKHIY"

    def test_get_us_ticker_track_only_returns_none(self, normalizer: TickerNormalizer) -> None:
        """Test get_us_ticker returns None for track-only tickers."""
        # Track-only tickers should return None
        assert normalizer.get_us_ticker("MDTKF") is None

    def test_get_venue(self, normalizer: TickerNormalizer) -> None:
        """Test venue detection."""
        assert normalizer.get_venue("NVDA") == "NASDAQ"
        # OTC tickers
        result = normalizer.normalize("005930.KS")
        assert result.venue == "OTC"

    def test_should_use_limit_order_liquid(self, normalizer: TickerNormalizer) -> None:
        """Test limit order recommendation for liquid stocks."""
        # Liquid US stocks don't need limit orders
        assert normalizer.should_use_limit_order("NVDA") is False
        assert normalizer.should_use_limit_order("ASML") is False

    def test_should_use_limit_order_illiquid(self, normalizer: TickerNormalizer) -> None:
        """Test limit order recommendation for illiquid stocks."""
        # Low liquidity OTC stocks should use limit orders
        assert normalizer.should_use_limit_order("005930.KS") is True

    def test_get_all_track_only(self, normalizer: TickerNormalizer) -> None:
        """Test getting all track-only tickers."""
        track_only = normalizer.get_all_track_only()

        assert "IBID" in track_only
        assert "MDTKF" in track_only
        assert "HNHPF" in track_only

    def test_get_all_tradeable_adrs(self, normalizer: TickerNormalizer) -> None:
        """Test getting all tradeable ADRs."""
        adrs = normalizer.get_all_tradeable_adrs()

        assert "SSNLF" in adrs
        assert "NTDOY" in adrs
        assert "SKHIY" in adrs


class TestTickerNormalizerEdgeCases:
    """Edge case tests for TickerNormalizer."""

    @pytest.fixture
    def normalizer(self) -> TickerNormalizer:
        """Create normalizer with real knowledge graph."""
        engine = GraphEngine("data/knowledge_graph_v1_2.json")
        engine.load_graph()
        return TickerNormalizer(engine)

    def test_normalize_unknown_non_us_ticker(self, normalizer: TickerNormalizer) -> None:
        """Test normalizing an unknown non-US ticker."""
        result = normalizer.normalize("9999.XX")

        # Should return original with warning
        assert result.symbol == "9999.XX"
        assert result.venue == "UNKNOWN"
        assert RiskFlag.LOW_LIQUIDITY in result.risk_flags

    def test_normalize_otc_ticker_directly(self, normalizer: TickerNormalizer) -> None:
        """Test normalizing an OTC ticker directly (not via foreign ticker)."""
        result = normalizer.normalize("SSNLF")

        assert result.symbol == "SSNLF"
        # Should detect it's an OTC ADR
        assert result.venue == "OTC" or result.is_adr is True
