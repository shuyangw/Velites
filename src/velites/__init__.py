"""
Velites - Quantamental Research Agent

The autonomous forward scout for the Homeguard execution system.
Identifies Information Asymmetry in the AI/Semiconductor supply chain
by analyzing technical literature and validating against market news.
"""

__version__ = "0.1.0"

from velites.config import settings, get_settings, Settings
from velites.logging import configure_logging, get_logger
from velites.exceptions import VelitesError

__all__ = [
    "settings",
    "get_settings",
    "Settings",
    "configure_logging",
    "get_logger",
    "VelitesError",
]
