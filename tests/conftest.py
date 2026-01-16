"""Pytest configuration and shared fixtures."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from velites.modules.scout.models import PaperObject, NewsObject, LiquidityStatus, MarketState
from velites.modules.mapper.models import EntityNode, EntityRole
from velites.modules.analyst.models import InnovationScore, SentimentScore


@pytest.fixture
def sample_paper() -> PaperObject:
    """Create a sample paper object."""
    return PaperObject(
        id="arxiv_2601.12345",
        title="Novel EUV Lithography Technique for Sub-2nm Nodes",
        abstract="We present a novel lithography technique using advanced EUV methods...",
        authors=["John Doe", "Jane Smith"],
        url="https://arxiv.org/abs/2601.12345",
        published_date=datetime(2026, 1, 16, 10, 0, 0),
        source="arxiv",
        categories=["cs.AR", "cs.AI"],
    )


@pytest.fixture
def sample_news() -> NewsObject:
    """Create a sample news object."""
    return NewsObject(
        id="news_tiingo_12345",
        headline="TSMC Reports Record Q4 Revenue Amid AI Chip Demand",
        summary="Taiwan Semiconductor Manufacturing Company reported...",
        source="Tiingo",
        url="https://example.com/news/12345",
        timestamp=datetime(2026, 1, 16, 8, 0, 0),
        tickers=["TSM", "NVDA"],
        keywords=["semiconductor", "AI", "revenue"],
    )


@pytest.fixture
def sample_market_state() -> MarketState:
    """Create a sample market state."""
    return MarketState(
        ticker="ASML",
        price=750.50,
        volume_30d_avg=1_500_000,
        spread_pct=0.05,
        liquidity_status=LiquidityStatus.HIGH,
        open=748.00,
        high=755.00,
        low=746.00,
        close=750.50,
        volume=1_200_000,
    )


@pytest.fixture
def sample_entity() -> EntityNode:
    """Create a sample entity node."""
    return EntityNode(
        ticker="NVDA",
        role=EntityRole.DIRECT,
        confidence=0.95,
        matched_term="Blackwell",
    )


@pytest.fixture
def sample_innovation_score() -> InnovationScore:
    """Create a sample innovation score."""
    return InnovationScore(
        score=0.85,
        reasoning="Novel architecture shows significant performance improvements",
        paper_id="arxiv_2601.12345",
        ticker="NVDA",
    )


@pytest.fixture
def sample_sentiment_score() -> SentimentScore:
    """Create a sample sentiment score."""
    return SentimentScore(
        score=0.1,
        hype_volume=0.5,
        is_veto=False,
        ticker="NVDA",
    )


@pytest.fixture
def knowledge_graph_path(tmp_path: Path) -> Path:
    """Create a temporary knowledge graph file with v1.2 structure."""
    graph_data = {
        "metadata": {
            "version": "1.2.0",
            "description": "Test knowledge graph"
        },
        "product_map": {
            "semiconductors": {
                "nvidia_ai_gpus": {
                    "H100": {"ticker": "NVDA", "role": "designer", "category": "ai_gpu"},
                    "B100": {"ticker": "NVDA", "role": "designer", "category": "ai_gpu"}
                }
            }
        },
        "supply_chain": {
            "NVDA": {
                "name": "NVIDIA Corporation",
                "tier1_suppliers": {
                    "TSM": {"role": "foundry"},
                    "SKHIY": {"role": "memory"}
                },
                "tier1_customers": {
                    "MSFT": {"products": ["H100"]}
                },
                "competitors": ["AMD", "INTC"]
            }
        },
        "ticker_normalization": {
            "mappings": {
                "005930.KS": {"us_adr": "SSNLF", "us_liquidity": "low"}
            },
            "trading_flags": {
                "tradeable_us": ["SSNLF"],
                "track_only": ["MDTKF"]
            }
        },
        "aliases": {
            "companies": {"nvidia": "NVDA", "tsmc": "TSM"},
            "products": {"hopper": "H100"}
        },
        "trading_signals": {
            "earnings_cascade": {
                "description": "Test signals",
                "patterns": [
                    {"trigger": "NVDA earnings beat", "watch": ["TSM"]}
                ]
            }
        }
    }

    graph_path = tmp_path / "knowledge_graph.json"
    with open(graph_path, "w") as f:
        json.dump(graph_data, f)

    return graph_path
