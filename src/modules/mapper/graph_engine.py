"""
The Entity Resolver - Knowledge Graph Engine

Maps unstructured text to specific graph nodes using fuzzy matching
and synonym resolution. Handles the v1.2 knowledge graph structure.
"""

import json
import re
from pathlib import Path
from typing import Any

from config import settings
from logging_config import get_logger
from modules.mapper.exceptions import EntityResolutionError, GraphTraversalError
from modules.mapper.models import EntityNode, EntityRole

logger = get_logger(__name__)


class GraphEngine:
    """
    Knowledge graph engine for entity resolution.

    Loads the knowledge graph from JSON and provides entity resolution
    capabilities using fuzzy matching and alias lookup.

    The v1.2 graph structure includes:
    - metadata: Version info
    - ticker_normalization: US ADR mappings and trading flags
    - product_map: Nested product -> ticker mappings
    - supply_chain: Company relationships (tier1_suppliers, tier1_customers)
    - aliases: Product and company name shortcuts
    - trading_signals: Signal patterns for trading strategies
    """

    def __init__(self, graph_path: str | None = None) -> None:
        """
        Initialize the graph engine.

        Args:
            graph_path: Path to knowledge graph JSON file
        """
        self.graph_path = Path(graph_path or settings.knowledge_graph_path)
        self._graph_data: dict | None = None

        # Indexed lookups (built on load)
        self._product_index: dict[str, dict] = {}  # product_name -> product_info
        self._company_aliases: dict[str, str] = {}  # alias -> ticker
        self._product_aliases: dict[str, str] = {}  # alias -> canonical_name
        self._supply_chain: dict[str, dict] = {}
        self._ticker_normalization: dict[str, dict] = {}
        self._trading_flags: dict[str, list[str]] = {}

    def load_graph(self) -> None:
        """Load the knowledge graph from JSON file and build indexes."""
        if not self.graph_path.exists():
            raise GraphTraversalError(f"Knowledge graph not found: {self.graph_path}")

        logger.info("loading_knowledge_graph", path=str(self.graph_path))

        with open(self.graph_path, encoding="utf-8") as f:
            self._graph_data = json.load(f)

        # Build indexes
        self._build_product_index()
        self._build_alias_index()
        self._load_supply_chain()
        self._load_ticker_normalization()

        logger.info(
            "knowledge_graph_loaded",
            version=self._graph_data.get("metadata", {}).get("version", "unknown"),
            products_indexed=len(self._product_index),
            company_aliases=len(self._company_aliases),
            supply_chain_entries=len(self._supply_chain),
        )

    def _build_product_index(self) -> None:
        """Build flat index from nested product_map for O(1) lookups."""
        product_map = self._graph_data.get("product_map", {})

        def _index_products(data: dict, path: str = "") -> None:
            for key, value in data.items():
                if isinstance(value, dict):
                    # Check if this is a product entry (has 'ticker' or 'tickers')
                    if "ticker" in value or "tickers" in value:
                        # This is a product - index it
                        product_name = key
                        self._product_index[product_name.lower()] = {
                            "name": product_name,
                            "path": path,
                            **value,
                        }
                    else:
                        # This is a category - recurse
                        new_path = f"{path}.{key}" if path else key
                        _index_products(value, new_path)

        _index_products(product_map)
        logger.debug("product_index_built", count=len(self._product_index))

    def _build_alias_index(self) -> None:
        """Build alias lookup indexes."""
        aliases = self._graph_data.get("aliases", {})

        # Company aliases (nvidia -> NVDA)
        self._company_aliases = {
            k.lower(): v for k, v in aliases.get("companies", {}).items()
        }

        # Product aliases (hopper -> H100)
        self._product_aliases = {
            k.lower(): v for k, v in aliases.get("products", {}).items()
        }

        logger.debug(
            "alias_index_built",
            companies=len(self._company_aliases),
            products=len(self._product_aliases),
        )

    def _load_supply_chain(self) -> None:
        """Load supply chain data."""
        self._supply_chain = self._graph_data.get("supply_chain", {})

    def _load_ticker_normalization(self) -> None:
        """Load ticker normalization mappings."""
        norm_data = self._graph_data.get("ticker_normalization", {})
        self._ticker_normalization = norm_data.get("mappings", {})
        self._trading_flags = norm_data.get("trading_flags", {})

    @property
    def graph_data(self) -> dict:
        """Get graph data, loading if necessary."""
        if self._graph_data is None:
            self.load_graph()
        return self._graph_data  # type: ignore

    def resolve_text(self, text: str) -> list[EntityNode]:
        """
        Map unstructured text to specific graph nodes.

        Args:
            text: Raw text to analyze (e.g., "HBM3e yields are low")

        Returns:
            List of EntityNode with resolved tickers and roles

        Example:
            >>> engine.resolve_text("New Blackwell delay rumors")
            [EntityNode(ticker="NVDA", role="direct", confidence=0.95),
             EntityNode(ticker="TSM", role="supplier", confidence=0.85)]
        """
        if self._graph_data is None:
            self.load_graph()

        entities: list[EntityNode] = []
        seen_tickers: set[str] = set()
        text_lower = text.lower()

        # 1. Check company aliases first (exact match)
        for alias, ticker in self._company_aliases.items():
            if self._word_in_text(alias, text_lower):
                if ticker not in seen_tickers:
                    entities.append(
                        EntityNode(
                            ticker=ticker,
                            role=EntityRole.DIRECT,
                            confidence=0.95,
                            matched_term=alias,
                        )
                    )
                    seen_tickers.add(ticker)

        # 2. Check product aliases and resolve to products
        for alias, product_name in self._product_aliases.items():
            if self._word_in_text(alias, text_lower):
                product_info = self._product_index.get(product_name.lower())
                if product_info:
                    ticker = product_info.get("ticker")
                    if ticker and ticker not in seen_tickers:
                        entities.append(
                            EntityNode(
                                ticker=ticker,
                                role=EntityRole.DIRECT,
                                confidence=0.90,
                                matched_term=alias,
                            )
                        )
                        seen_tickers.add(ticker)

        # 3. Scan for product names directly
        for product_name, product_info in self._product_index.items():
            if self._word_in_text(product_name, text_lower):
                ticker = product_info.get("ticker")
                tickers = product_info.get("tickers", [])

                if ticker and ticker not in seen_tickers:
                    entities.append(
                        EntityNode(
                            ticker=ticker,
                            role=EntityRole.DIRECT,
                            confidence=0.85,
                            matched_term=product_name,
                        )
                    )
                    seen_tickers.add(ticker)
                elif tickers:
                    # Multiple tickers (e.g., HBM3 -> SKHIY, MU, SSNLF)
                    for t in tickers:
                        if t not in seen_tickers:
                            entities.append(
                                EntityNode(
                                    ticker=t,
                                    role=EntityRole.DIRECT,
                                    confidence=0.80,
                                    matched_term=product_name,
                                )
                            )
                            seen_tickers.add(t)

        # 4. Try fuzzy matching if no exact matches found
        if not entities:
            fuzzy_results = self._fuzzy_search(text_lower)
            for result in fuzzy_results:
                if result["ticker"] not in seen_tickers:
                    entities.append(
                        EntityNode(
                            ticker=result["ticker"],
                            role=EntityRole.DIRECT,
                            confidence=result["confidence"],
                            matched_term=result["matched_term"],
                        )
                    )
                    seen_tickers.add(result["ticker"])

        # 5. Expand with suppliers for primary entities
        primary_entities = [e for e in entities if e.confidence >= 0.80]
        for entity in primary_entities:
            suppliers = self.get_tier1_suppliers(entity.ticker)
            for supplier_ticker, supplier_info in suppliers.items():
                if supplier_ticker not in seen_tickers:
                    # Lower confidence for derived relationships
                    entities.append(
                        EntityNode(
                            ticker=supplier_ticker,
                            role=EntityRole.SUPPLIER,
                            confidence=0.70,
                            matched_term=f"supplier of {entity.ticker}",
                        )
                    )
                    seen_tickers.add(supplier_ticker)

        return entities

    def _word_in_text(self, word: str, text: str) -> bool:
        """Check if word appears in text as a whole word."""
        # Use word boundaries for short terms, substring for longer ones
        if len(word) <= 3:
            pattern = rf"\b{re.escape(word)}\b"
            return bool(re.search(pattern, text, re.IGNORECASE))
        return word in text

    def _fuzzy_search(
        self, text: str, threshold: float = 0.85
    ) -> list[dict[str, Any]]:
        """
        Perform fuzzy matching on text against known products and companies.

        Args:
            text: Text to search
            threshold: Minimum similarity threshold (0-1)

        Returns:
            List of matches with ticker, confidence, and matched_term
        """
        results = []

        try:
            from rapidfuzz import fuzz
        except ImportError:
            logger.warning("rapidfuzz_not_installed", msg="Fuzzy matching disabled")
            return results

        # Extract potential terms from text (words of 3+ chars)
        words = re.findall(r"\b\w{3,}\b", text.lower())

        # Check against product names
        for word in words:
            for product_name, product_info in self._product_index.items():
                ratio = fuzz.ratio(word, product_name) / 100.0
                if ratio >= threshold:
                    ticker = product_info.get("ticker")
                    if ticker:
                        results.append({
                            "ticker": ticker,
                            "confidence": ratio * 0.9,  # Discount fuzzy matches
                            "matched_term": product_name,
                        })

            # Check against company aliases
            for alias, ticker in self._company_aliases.items():
                ratio = fuzz.ratio(word, alias) / 100.0
                if ratio >= threshold:
                    results.append({
                        "ticker": ticker,
                        "confidence": ratio * 0.9,
                        "matched_term": alias,
                    })

        # Deduplicate by ticker, keeping highest confidence
        ticker_best: dict[str, dict] = {}
        for r in results:
            ticker = r["ticker"]
            if ticker not in ticker_best or r["confidence"] > ticker_best[ticker]["confidence"]:
                ticker_best[ticker] = r

        return list(ticker_best.values())

    def get_tier1_suppliers(self, ticker: str) -> dict[str, dict]:
        """
        Get tier 1 suppliers for a ticker.

        Args:
            ticker: Company ticker symbol

        Returns:
            Dict of supplier_ticker -> supplier_info
        """
        if self._graph_data is None:
            self.load_graph()

        company = self._supply_chain.get(ticker, {})
        return company.get("tier1_suppliers", {})

    def get_tier1_customers(self, ticker: str) -> dict[str, dict]:
        """
        Get tier 1 customers for a ticker.

        Args:
            ticker: Company ticker symbol

        Returns:
            Dict of customer_ticker -> customer_info
        """
        if self._graph_data is None:
            self.load_graph()

        company = self._supply_chain.get(ticker, {})
        return company.get("tier1_customers", {})

    def get_competitors(self, ticker: str) -> list[str]:
        """
        Get competitors for a ticker.

        Args:
            ticker: Company ticker symbol

        Returns:
            List of competitor ticker symbols
        """
        if self._graph_data is None:
            self.load_graph()

        company = self._supply_chain.get(ticker, {})
        return company.get("competitors", [])

    def get_company_info(self, ticker: str) -> dict | None:
        """
        Get full company info from supply chain.

        Args:
            ticker: Company ticker symbol

        Returns:
            Company info dict or None
        """
        if self._graph_data is None:
            self.load_graph()

        return self._supply_chain.get(ticker)

    def get_product_info(self, product_name: str) -> dict | None:
        """
        Get product info by name.

        Args:
            product_name: Product name (e.g., "H100", "Blackwell")

        Returns:
            Product info dict or None
        """
        if self._graph_data is None:
            self.load_graph()

        # Check direct match
        info = self._product_index.get(product_name.lower())
        if info:
            return info

        # Check aliases
        canonical = self._product_aliases.get(product_name.lower())
        if canonical:
            return self._product_index.get(canonical.lower())

        return None

    def resolve_company_alias(self, name: str) -> str | None:
        """
        Resolve a company name/alias to its ticker.

        Args:
            name: Company name or alias

        Returns:
            Ticker symbol or None
        """
        if self._graph_data is None:
            self.load_graph()

        return self._company_aliases.get(name.lower())

    def get_trading_signals(self, trigger: str) -> list[dict]:
        """
        Get trading signal patterns that match a trigger.

        Args:
            trigger: Trigger event description

        Returns:
            List of matching signal patterns
        """
        if self._graph_data is None:
            self.load_graph()

        signals = self._graph_data.get("trading_signals", {})
        matches = []
        trigger_lower = trigger.lower()

        for signal_type, signal_data in signals.items():
            patterns = signal_data.get("patterns", [])
            for pattern in patterns:
                pattern_trigger = pattern.get("trigger", "").lower()
                if any(word in trigger_lower for word in pattern_trigger.split()):
                    matches.append({
                        "type": signal_type,
                        "description": signal_data.get("description", ""),
                        **pattern,
                    })

        return matches

    def get_small_mid_cap_suppliers(self, category: str | None = None) -> dict:
        """
        Get small/mid-cap supplier opportunities.

        Args:
            category: Optional category filter (e.g., "semiconductor_equipment")

        Returns:
            Dict of suppliers by category
        """
        if self._graph_data is None:
            self.load_graph()

        suppliers = self._graph_data.get("small_mid_cap_suppliers", {})

        if category:
            return {category: suppliers.get(category, {})}
        return suppliers

    def get_emerging_materials(self) -> dict:
        """Get emerging materials companies (glass substrates, packaging, etc.)."""
        if self._graph_data is None:
            self.load_graph()

        return self._graph_data.get("emerging_materials", {})
