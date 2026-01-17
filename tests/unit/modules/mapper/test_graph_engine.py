"""Tests for Knowledge Graph Engine."""

from pathlib import Path

import pytest

from modules.mapper.graph_engine import GraphEngine
from modules.mapper.exceptions import GraphTraversalError
from modules.mapper.models import EntityRole


class TestGraphEngine:
    """Tests for GraphEngine class."""

    def test_load_graph_success(self, knowledge_graph_path: Path) -> None:
        """Test successful graph loading."""
        engine = GraphEngine(str(knowledge_graph_path))
        engine.load_graph()

        assert engine._graph_data is not None
        assert len(engine._product_index) > 0

    def test_load_graph_file_not_found(self, tmp_path: Path) -> None:
        """Test graph loading with missing file."""
        engine = GraphEngine(str(tmp_path / "nonexistent.json"))

        with pytest.raises(GraphTraversalError):
            engine.load_graph()

    def test_graph_data_property_loads_automatically(self, knowledge_graph_path: Path) -> None:
        """Test that graph_data property auto-loads."""
        engine = GraphEngine(str(knowledge_graph_path))

        # Should auto-load on first access
        data = engine.graph_data

        assert data is not None
        assert "product_map" in data


class TestGraphEngineWithRealData:
    """Tests using the actual knowledge graph file."""

    @pytest.fixture
    def engine(self) -> GraphEngine:
        """Create engine with real knowledge graph."""
        # Use the actual data file
        engine = GraphEngine("data/knowledge_graph_v1_2.json")
        engine.load_graph()
        return engine

    def test_resolve_text_nvidia(self, engine: GraphEngine) -> None:
        """Test entity resolution for NVIDIA products."""
        entities = engine.resolve_text("New Blackwell delay rumors")

        # Should find NVDA via alias
        tickers = [e.ticker for e in entities]
        assert "NVDA" in tickers

    def test_resolve_text_h100(self, engine: GraphEngine) -> None:
        """Test entity resolution for H100."""
        entities = engine.resolve_text("H100 GPU shortage affecting cloud providers")

        tickers = [e.ticker for e in entities]
        assert "NVDA" in tickers

    def test_resolve_text_hbm(self, engine: GraphEngine) -> None:
        """Test entity resolution for HBM (multiple tickers)."""
        entities = engine.resolve_text("HBM3e yields are low")

        tickers = [e.ticker for e in entities]
        # HBM3e maps to multiple memory makers
        assert any(t in tickers for t in ["SKHIY", "MU", "SSNLF"])

    def test_resolve_text_eda_tools(self, engine: GraphEngine) -> None:
        """Test entity resolution for EDA tools."""
        entities = engine.resolve_text("Synopsys Fusion Compiler used for chip design")

        tickers = [e.ticker for e in entities]
        assert "SNPS" in tickers

    def test_resolve_text_includes_suppliers(self, engine: GraphEngine) -> None:
        """Test that resolution includes supplier relationships."""
        entities = engine.resolve_text("NVIDIA announces new B200 GPU")

        # Should include NVDA and its suppliers
        tickers = [e.ticker for e in entities]
        assert "NVDA" in tickers

        # Check for supplier relationships
        roles = {e.ticker: e.role for e in entities}
        supplier_tickers = [t for t, r in roles.items() if r == EntityRole.SUPPLIER]
        # TSM is a key supplier to NVDA
        assert "TSM" in supplier_tickers or len(supplier_tickers) > 0

    def test_get_tier1_suppliers(self, engine: GraphEngine) -> None:
        """Test getting tier 1 suppliers."""
        suppliers = engine.get_tier1_suppliers("NVDA")

        assert "TSM" in suppliers
        assert "SKHIY" in suppliers
        assert suppliers["TSM"]["role"] == "foundry"

    def test_get_tier1_customers(self, engine: GraphEngine) -> None:
        """Test getting tier 1 customers."""
        customers = engine.get_tier1_customers("NVDA")

        assert "MSFT" in customers
        assert "AMZN" in customers

    def test_get_competitors(self, engine: GraphEngine) -> None:
        """Test getting competitors."""
        competitors = engine.get_competitors("NVDA")

        assert "AMD" in competitors
        assert "INTC" in competitors

    def test_get_product_info(self, engine: GraphEngine) -> None:
        """Test getting product info."""
        info = engine.get_product_info("H100")

        assert info is not None
        assert info["ticker"] == "NVDA"
        assert info["category"] == "ai_gpu"

    def test_get_product_info_via_alias(self, engine: GraphEngine) -> None:
        """Test getting product info via alias."""
        info = engine.get_product_info("hopper")

        assert info is not None
        assert info["ticker"] == "NVDA"

    def test_resolve_company_alias(self, engine: GraphEngine) -> None:
        """Test company alias resolution."""
        assert engine.resolve_company_alias("nvidia") == "NVDA"
        assert engine.resolve_company_alias("tsmc") == "TSM"
        assert engine.resolve_company_alias("synopsys") == "SNPS"

    def test_get_trading_signals(self, engine: GraphEngine) -> None:
        """Test trading signal lookup."""
        signals = engine.get_trading_signals("NVDA earnings beat")

        assert len(signals) > 0
        # Should match earnings_cascade pattern
        assert any(s["type"] == "earnings_cascade" for s in signals)

    def test_get_small_mid_cap_suppliers(self, engine: GraphEngine) -> None:
        """Test small/mid-cap supplier lookup."""
        suppliers = engine.get_small_mid_cap_suppliers("semiconductor_equipment")

        assert "semiconductor_equipment" in suppliers
        equip = suppliers["semiconductor_equipment"]
        assert "ENTG" in equip
        assert "PLAB" in equip

    def test_get_emerging_materials(self, engine: GraphEngine) -> None:
        """Test emerging materials lookup."""
        materials = engine.get_emerging_materials()

        assert "glass_substrates" in materials
        assert "packaging_films" in materials
        assert "GLW" in materials["glass_substrates"]
