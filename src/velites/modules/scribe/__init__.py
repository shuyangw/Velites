"""
Scribe Module - Logging and Persistence

The "Black Box" of Velites. Maintains persistent records for backtesting
and analysis.

Components:
- Journal (journal): Signal and outcome tracking database
"""

from velites.modules.scribe.journal import Journal

__all__ = ["Journal"]
