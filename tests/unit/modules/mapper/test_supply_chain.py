"""Tests for Supply Chain Navigator."""

from pathlib import Path

import pytest

from modules.mapper.exceptions import GraphTraversalError
from modules.mapper.graph_engine import GraphEngine
from modules.mapper.models import DependencyMap
from modules.mapper.supply_chain import (
    BOTTLENECK_MARKET_SHARE_THRESHOLD,
    TOOL_MAKER_ROLES,
    SupplyChainNavigator,
)


class TestSupplyChainNavigator:
    """Tests for SupplyChainNavigator class with fixtures."""

    @pytest.fixture
    def navigator(self, knowledge_graph_path: Path) -> SupplyChainNavigator:
        """Create a navigator with test knowledge graph."""
        engine = GraphEngine(str(knowledge_graph_path))
        engine.load_graph()
        return SupplyChainNavigator(engine)

    def test_get_competitors_returns_list(self, navigator: SupplyChainNavigator) -> None:
        """Test that get_competitors returns a list."""
        competitors = navigator.get_competitors("NVDA")
        assert isinstance(competitors, list)
        assert "AMD" in competitors
        assert "INTC" in competitors

    def test_get_competitors_unknown_ticker_returns_empty(
        self, navigator: SupplyChainNavigator
    ) -> None:
        """Test that get_competitors returns empty list for unknown ticker."""
        competitors = navigator.get_competitors("UNKNOWN")
        assert competitors == []

    def test_get_tool_makers_returns_empty_for_no_tools(
        self, navigator: SupplyChainNavigator
    ) -> None:
        """Test tool makers for ticker with no EDA/equipment/IP suppliers."""
        # In test fixture, NVDA suppliers are TSM (foundry) and SKHIY (memory)
        tool_makers = navigator.get_tool_makers("NVDA")
        assert tool_makers == []

    def test_get_upstream_depth_zero(self, navigator: SupplyChainNavigator) -> None:
        """Test that depth=0 returns empty list."""
        upstream = navigator.get_upstream("NVDA", max_depth=0)
        assert upstream == []

    def test_get_upstream_depth_one(self, navigator: SupplyChainNavigator) -> None:
        """Test that depth=1 returns tier1 suppliers only."""
        upstream = navigator.get_upstream("NVDA", max_depth=1)
        assert "TSM" in upstream
        assert "SKHIY" in upstream

    def test_get_downstream_depth_zero(self, navigator: SupplyChainNavigator) -> None:
        """Test that depth=0 returns empty list."""
        downstream = navigator.get_downstream("NVDA", max_depth=0)
        assert downstream == []

    def test_get_downstream_depth_one(self, navigator: SupplyChainNavigator) -> None:
        """Test that depth=1 returns tier1 customers."""
        downstream = navigator.get_downstream("NVDA", max_depth=1)
        assert "MSFT" in downstream

    def test_get_dependencies_returns_dependency_map(self, navigator: SupplyChainNavigator) -> None:
        """Test that get_dependencies returns a DependencyMap."""
        deps = navigator.get_dependencies("NVDA")
        assert isinstance(deps, DependencyMap)
        assert deps.primary_ticker == "NVDA"

    def test_get_dependencies_includes_suppliers(self, navigator: SupplyChainNavigator) -> None:
        """Test that dependency map includes tier1 suppliers."""
        deps = navigator.get_dependencies("NVDA")
        assert "TSM" in deps.tier1_suppliers
        assert "SKHIY" in deps.tier1_suppliers

    def test_get_dependencies_includes_customers(self, navigator: SupplyChainNavigator) -> None:
        """Test that dependency map includes customers."""
        deps = navigator.get_dependencies("NVDA")
        assert "MSFT" in deps.customers

    def test_get_dependencies_includes_competitors(self, navigator: SupplyChainNavigator) -> None:
        """Test that dependency map includes competitors."""
        deps = navigator.get_dependencies("NVDA")
        assert "AMD" in deps.competitors
        assert "INTC" in deps.competitors

    def test_get_dependencies_unknown_ticker_raises(self, navigator: SupplyChainNavigator) -> None:
        """Test that unknown ticker raises GraphTraversalError."""
        with pytest.raises(GraphTraversalError, match="not found"):
            navigator.get_dependencies("UNKNOWN_TICKER")


class TestParseMarketShare:
    """Tests for _parse_market_share helper method."""

    @pytest.fixture
    def navigator(self, knowledge_graph_path: Path) -> SupplyChainNavigator:
        """Create a navigator for testing helper methods."""
        engine = GraphEngine(str(knowledge_graph_path))
        engine.load_graph()
        return SupplyChainNavigator(engine)

    def test_parse_range_returns_upper_bound(self, navigator: SupplyChainNavigator) -> None:
        """Test that range format returns upper bound."""
        assert navigator._parse_market_share("57-62%") == 62.0

    def test_parse_approximate_returns_value(self, navigator: SupplyChainNavigator) -> None:
        """Test that approximate format returns the value."""
        assert navigator._parse_market_share("~99%") == 99.0

    def test_parse_simple_percentage(self, navigator: SupplyChainNavigator) -> None:
        """Test simple percentage format."""
        assert navigator._parse_market_share("21%") == 21.0

    def test_parse_percentage_in_note(self, navigator: SupplyChainNavigator) -> None:
        """Test percentage embedded in note text."""
        assert navigator._parse_market_share("99% market share in ABF") == 99.0

    def test_parse_empty_string_returns_none(self, navigator: SupplyChainNavigator) -> None:
        """Test that empty string returns None."""
        assert navigator._parse_market_share("") is None

    def test_parse_none_returns_none(self, navigator: SupplyChainNavigator) -> None:
        """Test that None returns None."""
        assert navigator._parse_market_share(None) is None

    def test_parse_no_percentage_returns_none(self, navigator: SupplyChainNavigator) -> None:
        """Test that string without percentage returns None."""
        assert navigator._parse_market_share("Primary HBM supplier") is None

    def test_parse_decimal_percentage(self, navigator: SupplyChainNavigator) -> None:
        """Test decimal percentage format."""
        assert navigator._parse_market_share("57.5%") == 57.5

    def test_parse_range_with_decimals(self, navigator: SupplyChainNavigator) -> None:
        """Test range format with decimals."""
        assert navigator._parse_market_share("15.5-20.5%") == 20.5


class TestSupplyChainNavigatorWithRealData:
    """Tests using the actual knowledge graph file."""

    @pytest.fixture
    def navigator(self) -> SupplyChainNavigator:
        """Create navigator with real knowledge graph."""
        engine = GraphEngine("data/knowledge_graph_v1_2.json")
        engine.load_graph()
        return SupplyChainNavigator(engine)

    def test_get_dependencies_nvda(self, navigator: SupplyChainNavigator) -> None:
        """Test full dependency map for NVIDIA."""
        deps = navigator.get_dependencies("NVDA")

        assert deps.primary_ticker == "NVDA"
        assert "TSM" in deps.tier1_suppliers
        assert "SKHIY" in deps.tier1_suppliers
        assert "MSFT" in deps.customers or "AMZN" in deps.customers
        assert "AMD" in deps.competitors

    def test_get_competitors_nvda(self, navigator: SupplyChainNavigator) -> None:
        """Test NVDA competitors include AMD and INTC."""
        competitors = navigator.get_competitors("NVDA")
        assert "AMD" in competitors
        assert "INTC" in competitors

    def test_get_tool_makers_nvda(self, navigator: SupplyChainNavigator) -> None:
        """Test NVDA tool makers include EDA providers."""
        tool_makers = navigator.get_tool_makers("NVDA")
        # NVDA uses SNPS and CDNS for EDA, RMBS for IP
        assert "SNPS" in tool_makers
        assert "CDNS" in tool_makers
        assert "RMBS" in tool_makers

    def test_get_tool_makers_tsm(self, navigator: SupplyChainNavigator) -> None:
        """Test TSM tool makers include equipment providers."""
        tool_makers = navigator.get_tool_makers("TSM")
        # TSM uses equipment from AMAT, LRCX, KLAC, TOELY
        assert "AMAT" in tool_makers
        assert "LRCX" in tool_makers
        assert "KLAC" in tool_makers

    def test_identify_bottlenecks_nvda(self, navigator: SupplyChainNavigator) -> None:
        """Test that TSM is identified as bottleneck for NVDA (sole source)."""
        bottlenecks = navigator.identify_bottlenecks("NVDA")
        assert "TSM" in bottlenecks  # sole source for foundry

    def test_identify_bottlenecks_tsm(self, navigator: SupplyChainNavigator) -> None:
        """Test bottleneck identification for TSM."""
        bottlenecks = navigator.identify_bottlenecks("TSM")
        # AJINY has 99% market share in ABF
        assert "AJINY" in bottlenecks

    def test_get_upstream_depth_1(self, navigator: SupplyChainNavigator) -> None:
        """Test upstream at depth 1 returns tier1 suppliers."""
        upstream = navigator.get_upstream("NVDA", max_depth=1)
        assert "TSM" in upstream
        assert "SKHIY" in upstream
        assert "SNPS" in upstream

    def test_get_upstream_depth_2_includes_tier2(self, navigator: SupplyChainNavigator) -> None:
        """Test upstream at depth 2 includes tier2 suppliers."""
        upstream = navigator.get_upstream("NVDA", max_depth=2)
        # Tier1: TSM is a supplier
        assert "TSM" in upstream
        # Tier2: TSM's suppliers should be included
        assert "ASML" in upstream or "AMAT" in upstream

    def test_get_upstream_no_cycles(self, navigator: SupplyChainNavigator) -> None:
        """Test that upstream traversal has no duplicate tickers."""
        upstream = navigator.get_upstream("NVDA", max_depth=3)
        assert len(upstream) == len(set(upstream))

    def test_get_downstream_nvda(self, navigator: SupplyChainNavigator) -> None:
        """Test downstream customers for NVDA."""
        downstream = navigator.get_downstream("NVDA", max_depth=1)
        assert "MSFT" in downstream
        assert "AMZN" in downstream
        assert "META" in downstream

    def test_get_downstream_snps(self, navigator: SupplyChainNavigator) -> None:
        """Test downstream customers for SNPS (EDA tool maker)."""
        downstream = navigator.get_downstream("SNPS", max_depth=1)
        # Chip companies are customers of EDA tools
        assert "NVDA" in downstream
        assert "AMD" in downstream

    def test_get_downstream_leaf_node(self, navigator: SupplyChainNavigator) -> None:
        """Test downstream for a customer without further customers."""
        # MSFT is primarily a customer, doesn't have chip customers
        downstream = navigator.get_downstream("MSFT", max_depth=1)
        # Should be empty or minimal
        assert isinstance(downstream, list)

    def test_dependencies_include_tool_makers(self, navigator: SupplyChainNavigator) -> None:
        """Test that dependency map includes tool_makers field."""
        deps = navigator.get_dependencies("NVDA")
        assert len(deps.tool_makers) > 0
        assert "SNPS" in deps.tool_makers

    def test_dependencies_include_bottlenecks(self, navigator: SupplyChainNavigator) -> None:
        """Test that dependency map includes critical_bottlenecks."""
        deps = navigator.get_dependencies("NVDA")
        assert len(deps.critical_bottlenecks) > 0
        assert "TSM" in deps.critical_bottlenecks

    def test_dependencies_include_tier2_suppliers(self, navigator: SupplyChainNavigator) -> None:
        """Test that dependency map includes tier2 suppliers."""
        deps = navigator.get_dependencies("NVDA")
        # Tier2 should include TSM's suppliers
        assert len(deps.tier2_suppliers) > 0
        # ASML supplies TSM which supplies NVDA
        assert "ASML" in deps.tier2_suppliers


class TestConstants:
    """Tests for module constants."""

    def test_tool_maker_roles(self) -> None:
        """Test TOOL_MAKER_ROLES constant."""
        assert "eda" in TOOL_MAKER_ROLES
        assert "equipment" in TOOL_MAKER_ROLES
        assert "ip" in TOOL_MAKER_ROLES

    def test_bottleneck_threshold(self) -> None:
        """Test BOTTLENECK_MARKET_SHARE_THRESHOLD constant."""
        assert BOTTLENECK_MARKET_SHARE_THRESHOLD == 80.0
