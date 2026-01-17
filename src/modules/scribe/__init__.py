"""
Scribe Module - Logging and Persistence

The "Black Box" of Velites. Maintains persistent records for backtesting
and analysis.

Components:
- Journal (journal): Signal and outcome tracking database
- SignalRecord (db_models): SQLAlchemy ORM model for signals
"""

from modules.scribe.db_models import Base, SignalRecord
from modules.scribe.journal import Journal

__all__ = ["Journal", "SignalRecord", "Base"]
