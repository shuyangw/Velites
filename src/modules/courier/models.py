"""Data models for Courier module (signal dispatch)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from modules.mapper.models import RiskFlag


class SignalAction(str, Enum):
    """Trading signal action."""

    BUY = "BUY"
    BUY_LONG = "BUY_LONG"
    WAIT = "WAIT"
    IGNORE = "IGNORE"
    NO_GO = "NO_GO"


class OrderType(str, Enum):
    """Order type for execution."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class AlphaSignal(BaseModel):
    """Final trading signal from confluence engine."""

    signal_id: str = Field(..., description="Unique signal identifier")
    action: SignalAction = Field(..., description="Trading action")
    ticker: str = Field(..., description="Target ticker")
    venue: str = Field(default="NASDAQ")
    order_type: OrderType = Field(default=OrderType.LIMIT)
    limit_price: float | None = Field(default=None)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Signal reasoning")
    valid_until: datetime = Field(..., description="Signal expiration")
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    # Source tracking
    source_paper_id: str | None = Field(default=None)
    innovation_score: float | None = Field(default=None)
    sentiment_score: float | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "signal_id": "velites_001",
                "action": "BUY_LONG",
                "ticker": "ASML",
                "venue": "NASDAQ",
                "order_type": "LIMIT",
                "limit_price": 750.50,
                "confidence": 0.9,
                "reasoning": "ArXiv paper suggests new moat expansion. Market sentiment is quiet.",
                "valid_until": "2026-01-17T10:00:00Z",
                "risk_flags": [],
            }
        }
