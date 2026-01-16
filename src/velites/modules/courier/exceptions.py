"""Exceptions for Courier module (signal dispatch)."""

from velites.exceptions import VelitesError


class CourierError(VelitesError):
    """Base exception for Courier module errors."""

    pass


class LiquidityCheckError(CourierError):
    """Raised when liquidity check fails."""

    pass


class DispatchError(CourierError):
    """Raised when signal dispatch fails."""

    pass
