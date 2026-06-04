"""
Velites - Quantamental Research Agent

The autonomous forward scout for the Homeguard execution system.
Identifies Information Asymmetry in the AI/Semiconductor supply chain
by analyzing technical literature and validating against market news.
"""

__version__ = "0.1.0"

from config import Settings, get_settings, settings
from exceptions import VelitesError
from logging_config import configure_logging, get_logger

__all__ = [
    "settings",
    "get_settings",
    "Settings",
    "configure_logging",
    "get_logger",
    "VelitesError",
]
