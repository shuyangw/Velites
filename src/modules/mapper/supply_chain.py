"""
The Supply Chain Navigator - Dependency Traversal

Identifies second-order effects (The "Pick & Shovel" trade) by
traversing the knowledge graph to find suppliers, customers, and competitors.
"""

from __future__ import annotations

import re
from collections import deque
from typing import TYPE_CHECKING

from logging_config import get_logger
from modules.mapper.exceptions import GraphTraversalError
from modules.mapper.models import DependencyMap

if TYPE_CHECKING:
    from modules.mapper.graph_engine import GraphEngine

logger = get_logger(__name__)

# Constants
TOOL_MAKER_ROLES = {"eda", "equipment", "ip"}
BOTTLENECK_MARKET_SHARE_THRESHOLD = 80.0


class SupplyChainNavigator:
    """
    Navigates the supply chain relationships in the knowledge graph.

    Identifies upstream suppliers, downstream customers, and lateral
    competitors/tool makers for a given ticker.
    """

    def __init__(self, graph_engine: GraphEngine) -> None:
        """
        Initialize the supply chain navigator.

        Args:
            graph_engine: Loaded GraphEngine instance
        """
        self.graph_engine = graph_engine

    def _parse_market_share(self, value: str | None) -> float | None:
        """
        Parse market share string into float.

        Handles formats like "57-62%", "~99%", "21%", "99% market share in ABF".

        Args:
            value: Market share string

        Returns:
            Float percentage (e.g., 62.0 for "57-62%") or None if unparseable
        """
        if not value:
            return None

        # Extract percentage patterns
        # Match patterns like: "57-62%", "~99%", "21%", etc.
        patterns = [
            r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%",  # Range: "57-62%"
            r"~\s*(\d+(?:\.\d+)?)\s*%",  # Approximate: "~99%"
            r"(\d+(?:\.\d+)?)\s*%",  # Simple: "21%"
        ]

        # Try range pattern first (return upper bound)
        match = re.search(patterns[0], value)
        if match:
            return float(match.group(2))

        # Try approximate pattern
        match = re.search(patterns[1], value)
        if match:
            return float(match.group(1))

        # Try simple pattern
        match = re.search(patterns[2], value)
        if match:
            return float(match.group(1))

        return None

    def get_competitors(self, ticker: str) -> list[str]:
        """
        Get competitor tickers.

        Args:
            ticker: Company ticker to analyze

        Returns:
            List of competitor ticker symbols
        """
        return self.graph_engine.get_competitors(ticker)

    def get_tool_makers(self, ticker: str) -> list[str]:
        """
        Get tool/equipment maker tickers (e.g., EDA, inspection equipment, IP).

        Filters tier1 suppliers by role in {eda, equipment, ip}.

        Args:
            ticker: Ticker to analyze

        Returns:
            List of tool maker tickers
        """
        suppliers = self.graph_engine.get_tier1_suppliers(ticker)
        tool_makers = []

        for supplier_ticker, supplier_info in suppliers.items():
            role = supplier_info.get("role", "").lower()
            if role in TOOL_MAKER_ROLES:
                tool_makers.append(supplier_ticker)

        return tool_makers

    def identify_bottlenecks(self, ticker: str) -> list[str]:
        """
        Identify critical supply chain bottlenecks.

        A bottleneck is a supplier with:
        - revenue_concentration = "sole source", OR
        - market_share >= 80%

        Args:
            ticker: Ticker to analyze

        Returns:
            List of bottleneck supplier tickers
        """
        suppliers = self.graph_engine.get_tier1_suppliers(ticker)
        bottlenecks = []

        for supplier_ticker, supplier_info in suppliers.items():
            is_bottleneck = False

            # Check for sole source
            revenue_concentration = supplier_info.get("revenue_concentration", "")
            if revenue_concentration.lower() == "sole source":
                is_bottleneck = True

            # Check market share threshold
            market_share_str = supplier_info.get("market_share", "")
            market_share = self._parse_market_share(market_share_str)
            if market_share is not None and market_share >= BOTTLENECK_MARKET_SHARE_THRESHOLD:
                is_bottleneck = True

            # Also check the note field for market share info
            note = supplier_info.get("note", "")
            note_market_share = self._parse_market_share(note)
            if (
                note_market_share is not None
                and note_market_share >= BOTTLENECK_MARKET_SHARE_THRESHOLD
            ):
                is_bottleneck = True

            if is_bottleneck:
                bottlenecks.append(supplier_ticker)

        return bottlenecks

    def get_upstream(self, ticker: str, max_depth: int = 2) -> list[str]:
        """
        Get upstream suppliers for a ticker using BFS traversal.

        Args:
            ticker: Ticker to analyze
            max_depth: Maximum depth of supplier chain to traverse (0 = none, 1 = tier1 only)

        Returns:
            List of supplier tickers (deduplicated)
        """
        if max_depth <= 0:
            return []

        visited: set[str] = {ticker}
        result: list[str] = []
        queue: deque[tuple[str, int]] = deque([(ticker, 0)])

        while queue:
            current_ticker, depth = queue.popleft()

            if depth >= max_depth:
                continue

            suppliers = self.graph_engine.get_tier1_suppliers(current_ticker)
            for supplier_ticker in suppliers:
                if supplier_ticker not in visited:
                    visited.add(supplier_ticker)
                    result.append(supplier_ticker)
                    queue.append((supplier_ticker, depth + 1))

        return result

    def get_downstream(self, ticker: str, max_depth: int = 2) -> list[str]:
        """
        Get downstream customers for a ticker using BFS traversal.

        Args:
            ticker: Ticker to analyze
            max_depth: Maximum depth of customer chain

        Returns:
            List of customer tickers (deduplicated)
        """
        if max_depth <= 0:
            return []

        visited: set[str] = {ticker}
        result: list[str] = []
        queue: deque[tuple[str, int]] = deque([(ticker, 0)])

        while queue:
            current_ticker, depth = queue.popleft()

            if depth >= max_depth:
                continue

            customers = self.graph_engine.get_tier1_customers(current_ticker)
            for customer_ticker in customers:
                if customer_ticker not in visited:
                    visited.add(customer_ticker)
                    result.append(customer_ticker)
                    queue.append((customer_ticker, depth + 1))

        return result

    def _get_tier2_suppliers(self, tier1_tickers: list[str]) -> list[str]:
        """
        Get tier 2 suppliers (suppliers of tier 1 suppliers).

        Args:
            tier1_tickers: List of tier 1 supplier tickers

        Returns:
            List of tier 2 supplier tickers (deduplicated, excluding tier1)
        """
        tier1_set = set(tier1_tickers)
        tier2: set[str] = set()

        for tier1_ticker in tier1_tickers:
            suppliers = self.graph_engine.get_tier1_suppliers(tier1_ticker)
            for supplier_ticker in suppliers:
                if supplier_ticker not in tier1_set:
                    tier2.add(supplier_ticker)

        return list(tier2)

    def get_dependencies(self, ticker: str) -> DependencyMap:
        """
        Get full dependency map for a ticker.

        Args:
            ticker: Primary ticker to analyze (e.g., "NVDA")

        Returns:
            DependencyMap with all relationships

        Raises:
            GraphTraversalError: If ticker not found in knowledge graph

        Example:
            >>> navigator.get_dependencies("NVDA")
            DependencyMap(
                primary_ticker="NVDA",
                tier1_suppliers=["TSM", "SKHIY"],
                customers=["MSFT", "META"],
                tool_makers=["SNPS", "CAMT"]
            )
        """
        logger.info("traversing_supply_chain", ticker=ticker)

        # Check if ticker exists in graph
        company_info = self.graph_engine.get_company_info(ticker)
        if company_info is None:
            raise GraphTraversalError(f"Ticker '{ticker}' not found in knowledge graph")

        # Get tier 1 suppliers
        tier1_suppliers_dict = self.graph_engine.get_tier1_suppliers(ticker)
        tier1_suppliers = list(tier1_suppliers_dict.keys())

        # Get tier 2 suppliers
        tier2_suppliers = self._get_tier2_suppliers(tier1_suppliers)

        # Get customers (tier 1 only)
        customers_dict = self.graph_engine.get_tier1_customers(ticker)
        customers = list(customers_dict.keys())

        # Get competitors
        competitors = self.get_competitors(ticker)

        # Get tool makers (filtered from suppliers)
        tool_makers = self.get_tool_makers(ticker)

        # Identify bottlenecks
        bottlenecks = self.identify_bottlenecks(ticker)

        logger.info(
            "supply_chain_traversed",
            ticker=ticker,
            tier1_suppliers=len(tier1_suppliers),
            tier2_suppliers=len(tier2_suppliers),
            customers=len(customers),
            competitors=len(competitors),
            tool_makers=len(tool_makers),
            bottlenecks=len(bottlenecks),
        )

        return DependencyMap(
            primary_ticker=ticker,
            tier1_suppliers=tier1_suppliers,
            tier2_suppliers=tier2_suppliers,
            customers=customers,
            competitors=competitors,
            tool_makers=tool_makers,
            critical_bottlenecks=bottlenecks,
        )
