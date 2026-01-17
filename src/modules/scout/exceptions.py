"""Exceptions for Scout module (data ingestion)."""

from exceptions import VelitesError


class ScoutError(VelitesError):
    """Base exception for Scout module errors."""

    pass


class DataFetchError(ScoutError):
    """Raised when data fetching fails."""

    pass


class RateLimitError(ScoutError):
    """Raised when API rate limit is exceeded."""

    pass
