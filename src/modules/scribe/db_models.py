"""SQLAlchemy ORM models for Scribe module."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models."""

    pass


class SignalRecord(Base):
    """Persistent record of a trading signal."""

    __tablename__ = "signal_records"

    # Primary key - uses signal_id from AlphaSignal
    id = Column(String(64), primary_key=True)

    # Signal details
    ticker = Column(String(16), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text)
    source_paper_id = Column(String(128))

    # Price tracking
    market_price = Column(Float, nullable=False)
    outcome_price = Column(Float)
    outcome_date = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, nullable=False, index=True)

    # Composite index for common queries
    __table_args__ = (
        Index("ix_signal_ticker_created", "ticker", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert record to dictionary."""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "source_paper_id": self.source_paper_id,
            "market_price": self.market_price,
            "outcome_price": self.outcome_price,
            "outcome_date": self.outcome_date.isoformat() if self.outcome_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
