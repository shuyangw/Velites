"""Data models for Mapper module (knowledge graph and entity resolution)."""

from enum import Enum

from pydantic import BaseModel, Field


class EntityRole(str, Enum):
    """Role of an entity in the supply chain."""

    DIRECT = "direct"
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    TOOL_MAKER = "tool_maker"


class RiskFlag(str, Enum):
    """Risk flags for tradeable tickers."""

    LIMIT_ORDER_ONLY = "LIMIT_ORDER_ONLY"
    SMALL_CAP = "SMALL_CAP"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    OTC = "OTC"
    EARNINGS_APPROACHING = "EARNINGS_APPROACHING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


class EntityNode(BaseModel):
    """Resolved entity from text."""

    ticker: str = Field(..., description="Stock ticker symbol")
    role: EntityRole = Field(..., description="Role in the context")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence")
    matched_term: str | None = Field(default=None, description="Original term matched")


class DependencyMap(BaseModel):
    """Supply chain dependency mapping."""

    primary_ticker: str = Field(..., description="Primary ticker analyzed")
    tier1_suppliers: list[str] = Field(default_factory=list)
    tier2_suppliers: list[str] = Field(default_factory=list)
    customers: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    tool_makers: list[str] = Field(default_factory=list)
    critical_bottlenecks: list[str] = Field(default_factory=list)


class TradeableTicker(BaseModel):
    """Normalized tradeable ticker."""

    symbol: str = Field(..., description="US-tradeable symbol")
    original_symbol: str | None = Field(default=None, description="Original international symbol")
    venue: str = Field(default="NASDAQ", description="Trading venue")
    is_adr: bool = Field(default=False, description="Is an ADR")
    risk_flags: list[RiskFlag] = Field(default_factory=list)
