"""Data models for Scribe module (logging and auditing)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JournalEntryType(str, Enum):
    """Type of journal entry."""

    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_DISPATCHED = "signal_dispatched"
    ENTITY_RESOLVED = "entity_resolved"
    PAPER_PROCESSED = "paper_processed"
    NEWS_PROCESSED = "news_processed"
    ERROR = "error"
    AUDIT = "audit"


class JournalEntry(BaseModel):
    """Entry in the Scribe journal."""

    id: str = Field(..., description="Unique entry identifier")
    entry_type: JournalEntryType = Field(..., description="Type of entry")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    module: str = Field(..., description="Source module")
    message: str = Field(..., description="Entry message")
    data: dict | None = Field(default=None, description="Additional structured data")
    ticker: str | None = Field(default=None, description="Related ticker if applicable")
    signal_id: str | None = Field(default=None, description="Related signal ID if applicable")
