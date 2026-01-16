"""Exceptions for Analyst module (signal generation)."""

from velites.exceptions import VelitesError


class AnalystError(VelitesError):
    """Base exception for Analyst module errors."""

    pass


class LLMError(AnalystError):
    """Raised when LLM processing fails."""

    pass


class SentimentError(AnalystError):
    """Raised when sentiment analysis fails."""

    pass
