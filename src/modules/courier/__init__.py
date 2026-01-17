"""
Courier Module - Interface

The "Messenger" of Velites. Formats and delivers orders to Homeguard.
Does NOT execute trades - only dispatches instructions.

Components:
- Payload Formatter (dispatcher): Creates standardized JSON for Homeguard
- Liquidity Guard (liquidity_guard): Final check for tradeability
"""

from modules.courier.dispatcher import Dispatcher
from modules.courier.liquidity_guard import LiquidityGuard

__all__ = ["Dispatcher", "LiquidityGuard"]
