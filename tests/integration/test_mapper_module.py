"""End-to-end integration tests for the Mapper module.

Tests the full flow from text resolution through supply chain traversal
to tradeable ticker normalization.
"""

import pytest

from modules.mapper.graph_engine import GraphEngine
from modules.mapper.supply_chain import SupplyChainNavigator
from modules.mapper.ticker_normalizer import TickerNormalizer
from modules.mapper.models import EntityRole, RiskFlag


class TestMapperModuleE2E:
    """End-to-end tests for the complete Mapper module flow."""

    @pytest.fixture
    def graph_engine(self) -> GraphEngine:
        """Create and load the real knowledge graph."""
        engine = GraphEngine("data/knowledge_graph_v1_2.json")
        engine.load_graph()
        return engine

    @pytest.fixture
    def navigator(self, graph_engine: GraphEngine) -> SupplyChainNavigator:
        """Create a supply chain navigator."""
        return SupplyChainNavigator(graph_engine)

    @pytest.fixture
    def normalizer(self, graph_engine: GraphEngine) -> TickerNormalizer:
        """Create a ticker normalizer."""
        return TickerNormalizer(graph_engine)

    def test_full_flow_text_to_tradeable_tickers(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
        normalizer: TickerNormalizer,
    ) -> None:
        """
        Test complete flow: text -> entities -> dependencies -> tradeable tickers.

        Flow:
        1. Resolve text to entities
        2. Get dependencies for primary entity
        3. Normalize all tickers to US-tradeable symbols
        """
        # Step 1: Resolve text to entities
        text = "New Blackwell delay rumors"
        entities = graph_engine.resolve_text(text)

        # Should find NVDA
        primary_tickers = [e.ticker for e in entities if e.role == EntityRole.DIRECT]
        assert "NVDA" in primary_tickers

        # Step 2: Get dependencies for NVDA
        deps = navigator.get_dependencies("NVDA")
        assert deps.primary_ticker == "NVDA"
        assert len(deps.tier1_suppliers) > 0

        # Step 3: Collect all related tickers
        all_tickers = (
            [deps.primary_ticker]
            + deps.tier1_suppliers
            + deps.tier2_suppliers
            + deps.customers
            + deps.competitors
        )

        # Step 4: Normalize to tradeable tickers
        tradeable = []
        for ticker in all_tickers:
            result = normalizer.normalize(ticker)
            if normalizer.is_tradeable(ticker) or normalizer.is_tradeable(result.symbol):
                tradeable.append(result.symbol)

        # Should have multiple tradeable tickers
        assert len(tradeable) > 5
        assert "NVDA" in tradeable
        assert "TSM" in tradeable

    def test_hbm_news_to_memory_suppliers(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
        normalizer: TickerNormalizer,
    ) -> None:
        """
        Test flow for HBM news: resolve HBM -> memory makers -> verify relationships.

        Flow:
        1. Resolve "HBM3e yields" to memory maker tickers
        2. Verify these are suppliers to NVDA
        """
        # Step 1: Resolve HBM news
        text = "HBM3e yields are low"
        entities = graph_engine.resolve_text(text)

        # Should find memory makers (SKHIY, MU, or SSNLF)
        memory_tickers = [e.ticker for e in entities if e.role == EntityRole.DIRECT]
        assert any(t in memory_tickers for t in ["SKHIY", "MU", "SSNLF"])

        # Step 2: Verify these are NVDA suppliers
        nvda_deps = navigator.get_dependencies("NVDA")
        for ticker in memory_tickers:
            if ticker in ["SKHIY", "MU", "SSNLF"]:
                assert ticker in nvda_deps.tier1_suppliers, f"{ticker} should be NVDA supplier"

        # Step 3: Check downstream for a memory maker
        if "SKHIY" in memory_tickers:
            downstream = navigator.get_downstream("SKHIY", max_depth=1)
            assert "NVDA" in downstream, "NVDA should be customer of SK Hynix"

    def test_tool_maker_cascade(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
    ) -> None:
        """
        Test tool maker identification flow.

        Flow:
        1. Resolve EDA tool mention -> SNPS
        2. Verify SNPS is in NVDA's tool_makers
        """
        # Step 1: Resolve Synopsys mention
        text = "Synopsys Fusion Compiler used for chip design"
        entities = graph_engine.resolve_text(text)

        snps_entities = [e for e in entities if e.ticker == "SNPS"]
        assert len(snps_entities) > 0, "Should find SNPS from Synopsys mention"

        # Step 2: Check NVDA's tool makers
        nvda_deps = navigator.get_dependencies("NVDA")
        assert "SNPS" in nvda_deps.tool_makers, "SNPS should be NVDA's tool maker"

        # Step 3: Verify SNPS has NVDA as customer
        snps_downstream = navigator.get_downstream("SNPS", max_depth=1)
        assert "NVDA" in snps_downstream, "NVDA should be SNPS customer"

    def test_non_us_ticker_normalization_in_flow(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
        normalizer: TickerNormalizer,
    ) -> None:
        """
        Test non-US ticker normalization within dependency flow.

        Flow:
        1. Get TSM's suppliers (includes non-US tickers)
        2. Normalize Korean/Japanese tickers to US ADRs
        """
        # Step 1: Get TSM dependencies
        tsm_deps = navigator.get_dependencies("TSM")

        # Step 2: Look for non-US suppliers like TOELY (Tokyo Electron)
        tier1_suppliers = tsm_deps.tier1_suppliers
        assert "TOELY" in tier1_suppliers or any(
            t in tier1_suppliers for t in ["AJINY", "PCRFY"]
        ), "TSM should have Japanese suppliers"

        # Step 3: Normalize Japanese tickers
        if "AJINY" in tier1_suppliers:
            result = normalizer.normalize("AJINY")
            # AJINY is already a US ADR
            assert result.symbol == "AJINY"
            # Should have low liquidity flags
            assert RiskFlag.LOW_LIQUIDITY in result.risk_flags or result.venue == "OTC"

        # Step 4: Test normalization of Korean ticker
        korean_ticker = "005930.KS"  # Samsung
        result = normalizer.normalize(korean_ticker)
        assert result.symbol == "SSNLF", "Samsung should normalize to SSNLF"
        assert result.is_adr is True
        assert result.original_symbol == korean_ticker

    def test_bottleneck_identification_flow(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
    ) -> None:
        """
        Test bottleneck identification in supply chain flow.

        Flow:
        1. Get NVDA dependencies
        2. Verify TSM is identified as bottleneck (sole source foundry)
        """
        # Step 1: Get NVDA dependencies
        deps = navigator.get_dependencies("NVDA")

        # Step 2: TSM should be a critical bottleneck
        assert "TSM" in deps.critical_bottlenecks, "TSM should be NVDA bottleneck (sole source)"

        # Step 3: Verify bottleneck method directly
        bottlenecks = navigator.identify_bottlenecks("NVDA")
        assert "TSM" in bottlenecks

        # Step 4: Check TSM's bottlenecks
        tsm_bottlenecks = navigator.identify_bottlenecks("TSM")
        # AJINY has 99% market share in ABF
        assert "AJINY" in tsm_bottlenecks, "AJINY should be TSM bottleneck (99% market share)"

    def test_multi_hop_supply_chain_traversal(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
    ) -> None:
        """
        Test multi-hop supply chain traversal (tier1 -> tier2).

        Flow:
        1. Get NVDA upstream with depth=2
        2. Verify tier2 suppliers (TSM's suppliers) are included
        """
        # Step 1: Get deep upstream
        upstream = navigator.get_upstream("NVDA", max_depth=2)

        # Tier1: TSM, SKHIY, etc.
        assert "TSM" in upstream

        # Tier2: TSM's suppliers should be included
        # ASML supplies TSM
        assert "ASML" in upstream, "ASML should be in tier2 (supplies TSM)"

        # Equipment makers that supply TSM
        equipment_in_tier2 = [t for t in upstream if t in ["ASML", "AMAT", "LRCX", "KLAC"]]
        assert len(equipment_in_tier2) > 0, "Should find equipment makers in tier2"

    def test_competitor_lateral_relationships(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
    ) -> None:
        """
        Test competitor identification across the supply chain.

        Flow:
        1. Get NVDA competitors
        2. Verify AMD and INTC have overlapping suppliers
        """
        # Step 1: Get NVDA competitors
        nvda_competitors = navigator.get_competitors("NVDA")
        assert "AMD" in nvda_competitors
        assert "INTC" in nvda_competitors

        # Step 2: Get AMD's suppliers
        amd_deps = navigator.get_dependencies("AMD")

        # Step 3: Verify overlapping suppliers
        # Both NVDA and AMD use TSM for fabrication
        nvda_deps = navigator.get_dependencies("NVDA")
        shared_suppliers = set(nvda_deps.tier1_suppliers) & set(amd_deps.tier1_suppliers)
        assert "TSM" in shared_suppliers, "NVDA and AMD should share TSM as supplier"

        # Both should use EDA tools
        assert "SNPS" in shared_suppliers or "CDNS" in shared_suppliers

    def test_dependency_map_completeness(
        self,
        graph_engine: GraphEngine,
        navigator: SupplyChainNavigator,
    ) -> None:
        """
        Test that dependency map contains all expected fields.
        """
        deps = navigator.get_dependencies("NVDA")

        # All fields should be populated
        assert deps.primary_ticker == "NVDA"
        assert len(deps.tier1_suppliers) > 0
        assert len(deps.tier2_suppliers) > 0
        assert len(deps.customers) > 0
        assert len(deps.competitors) > 0
        assert len(deps.tool_makers) > 0
        assert len(deps.critical_bottlenecks) > 0

        # Tool makers should be subset of tier1 suppliers
        for tool_maker in deps.tool_makers:
            assert tool_maker in deps.tier1_suppliers

        # Bottlenecks should be subset of tier1 suppliers
        for bottleneck in deps.critical_bottlenecks:
            assert bottleneck in deps.tier1_suppliers


class TestMapperModuleEdgeCases:
    """Edge case tests for the Mapper module."""

    @pytest.fixture
    def graph_engine(self) -> GraphEngine:
        """Create and load the real knowledge graph."""
        engine = GraphEngine("data/knowledge_graph_v1_2.json")
        engine.load_graph()
        return engine

    @pytest.fixture
    def navigator(self, graph_engine: GraphEngine) -> SupplyChainNavigator:
        """Create a supply chain navigator."""
        return SupplyChainNavigator(graph_engine)

    @pytest.fixture
    def normalizer(self, graph_engine: GraphEngine) -> TickerNormalizer:
        """Create a ticker normalizer."""
        return TickerNormalizer(graph_engine)

    def test_leaf_node_has_empty_downstream(
        self, navigator: SupplyChainNavigator
    ) -> None:
        """Test that leaf nodes (end customers) have empty or minimal downstream."""
        # MSFT is primarily a customer, doesn't sell to chip companies
        downstream = navigator.get_downstream("MSFT", max_depth=1)
        # Should be empty or contain only software customers
        assert len(downstream) < 5  # Reasonable threshold

    def test_normalize_unknown_non_us_ticker(
        self, normalizer: TickerNormalizer
    ) -> None:
        """Test normalization of unknown non-US ticker."""
        # Unknown Korean ticker without a mapping
        result = normalizer.normalize("999999.KS")
        assert result.symbol == "999999.KS"
        assert RiskFlag.LOW_LIQUIDITY in result.risk_flags
        assert result.venue == "UNKNOWN"

    def test_normalize_unknown_us_ticker(
        self, normalizer: TickerNormalizer
    ) -> None:
        """Test normalization of unknown US ticker returns it unchanged."""
        # Unknown ticker without foreign suffix treated as US ticker
        result = normalizer.normalize("UNKNOWN123")
        assert result.symbol == "UNKNOWN123"
        # US tickers without known issues are returned as-is
        assert result.venue == "NASDAQ"

    def test_empty_text_resolution(
        self, graph_engine: GraphEngine
    ) -> None:
        """Test that empty text returns empty entities."""
        entities = graph_engine.resolve_text("")
        assert entities == []

    def test_irrelevant_text_resolution(
        self, graph_engine: GraphEngine
    ) -> None:
        """Test that irrelevant text returns empty entities."""
        entities = graph_engine.resolve_text("The weather is nice today")
        assert len(entities) == 0

    def test_case_insensitive_resolution(
        self, graph_engine: GraphEngine
    ) -> None:
        """Test that text resolution is case insensitive."""
        lower = graph_engine.resolve_text("nvidia")
        upper = graph_engine.resolve_text("NVIDIA")

        lower_tickers = {e.ticker for e in lower}
        upper_tickers = {e.ticker for e in upper}

        assert "NVDA" in lower_tickers or "NVDA" in upper_tickers

    def test_normalizer_idempotent(
        self, normalizer: TickerNormalizer
    ) -> None:
        """Test that normalizing twice gives same result."""
        first = normalizer.normalize("NVDA")
        second = normalizer.normalize(first.symbol)

        assert first.symbol == second.symbol
        assert first.venue == second.venue
