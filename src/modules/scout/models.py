"""Data models for Scout module (data ingestion)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class PaperObject(BaseModel):
    """Represents a technical paper from ArXiv or similar sources."""

    id: str = Field(..., description="Unique paper identifier (e.g., arxiv_2601.12345)")
    title: str = Field(..., description="Paper title")
    abstract: str = Field(..., description="Paper abstract text")
    authors: list[str] = Field(default_factory=list, description="List of author names")
    url: HttpUrl = Field(..., description="URL to the paper")
    published_date: datetime = Field(..., description="Publication date")
    source: str = Field(default="arxiv", description="Source of the paper")
    categories: list[str] = Field(default_factory=list, description="ArXiv categories")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "arxiv_2601.12345",
                "title": "Novel EUV Lithography Technique for Sub-2nm Nodes",
                "abstract": "We present a novel lithography technique...",
                "authors": ["John Doe", "Jane Smith"],
                "url": "https://arxiv.org/abs/2601.12345",
                "published_date": "2026-01-16T10:00:00Z",
                "source": "arxiv",
                "categories": ["cs.AR", "cs.AI"],
            }
        }


class NewsObject(BaseModel):
    """Represents a news article from various sources."""

    id: str = Field(..., description="Unique news identifier")
    headline: str = Field(..., description="News headline")
    summary: str = Field(..., description="Brief summary of the article")
    content: str | None = Field(default=None, description="Full article content if available")
    source: str = Field(..., description="News source name")
    url: HttpUrl | None = Field(default=None, description="URL to the article")
    timestamp: datetime = Field(..., description="Publication timestamp")
    tickers: list[str] = Field(default_factory=list, description="Related stock tickers")
    keywords: list[str] = Field(default_factory=list, description="Extracted keywords")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "news_tiingo_12345",
                "headline": "TSMC Reports Record Q4 Revenue Amid AI Chip Demand",
                "summary": "Taiwan Semiconductor Manufacturing Company...",
                "content": None,
                "source": "Tiingo",
                "url": "https://example.com/news/12345",
                "timestamp": "2026-01-16T08:00:00Z",
                "tickers": ["TSM", "NVDA"],
                "keywords": ["semiconductor", "AI", "revenue"],
            }
        }


class LiquidityStatus(str, Enum):
    """Liquidity status classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ILLIQUID = "illiquid"


class MarketState(BaseModel):
    """Current market state for a ticker."""

    ticker: str = Field(..., description="Stock ticker symbol")
    price: float = Field(..., description="Current/last price")
    volume_30d_avg: float = Field(..., description="30-day average volume")
    spread_pct: float = Field(..., description="Bid-ask spread as percentage")
    liquidity_status: LiquidityStatus = Field(..., description="Liquidity classification")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # OHLCV data
    open: float | None = Field(default=None)
    high: float | None = Field(default=None)
    low: float | None = Field(default=None)
    close: float | None = Field(default=None)
    volume: int | None = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "ASML",
                "price": 750.50,
                "volume_30d_avg": 1_500_000,
                "spread_pct": 0.05,
                "liquidity_status": "high",
                "timestamp": "2026-01-16T15:30:00Z",
            }
        }
