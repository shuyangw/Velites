"""Exceptions for Scribe module (logging and auditing)."""

from velites.exceptions import VelitesError


class ScribeError(VelitesError):
    """Base exception for Scribe module errors."""

    pass


class JournalWriteError(ScribeError):
    """Raised when journal write fails."""

    pass
