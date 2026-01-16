"""Exceptions for Mapper module (knowledge graph)."""

from velites.exceptions import VelitesError


class MapperError(VelitesError):
    """Base exception for Mapper module errors."""

    pass


class EntityResolutionError(MapperError):
    """Raised when entity resolution fails."""

    pass


class GraphTraversalError(MapperError):
    """Raised when knowledge graph traversal fails."""

    pass
