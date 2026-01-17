"""
The Liquidity Guard - Final Tradeability Check

Hard rejection of un-tradeable assets before dispatch.
"""

from config import settings
from logging_config import get_logger
from modules.courier.exceptions import LiquidityCheckError
from modules.scout.models import MarketState
from modules.courier.models import AlphaSignal, SignalAction

logger = get_logger(__name__)


class LiquidityGuard:
    """
    Final liquidity check before signal dispatch.

    Rules:
    - If Spread > 2%, convert signal to NO_GO
    - If Volume < $500k, convert signal to NO_GO
    """

    def __init__(self) -> None:
        self.max_spread_pct = settings.max_spread_pct
        self.min_volume_usd = settings.min_volume_usd

    def check_liquidity(self, market_state: MarketState) -> tuple[bool, list[str]]:
        """
        Check if a ticker passes liquidity requirements.

        Args:
            market_state: Current market state for the ticker

        Returns:
            Tuple of (passes: bool, failure_reasons: list[str])
        """
        failures = []

        # Check spread
        if market_state.spread_pct > self.max_spread_pct:
            failures.append(
                f"Spread {market_state.spread_pct:.2f}% exceeds max {self.max_spread_pct}%"
            )

        # Check volume
        volume_usd = market_state.volume_30d_avg * market_state.price
        if volume_usd < self.min_volume_usd:
            failures.append(
                f"Volume ${volume_usd:,.0f} below min ${self.min_volume_usd:,.0f}"
            )

        passes = len(failures) == 0

        if not passes:
            logger.warning(
                "liquidity_check_failed",
                ticker=market_state.ticker,
                failures=failures,
            )

        return passes, failures

    def validate_signal(
        self, signal: AlphaSignal, market_state: MarketState
    ) -> AlphaSignal:
        """
        Validate a signal against liquidity requirements.

        Args:
            signal: Signal to validate
            market_state: Current market state

        Returns:
            Original signal if passes, or modified NO_GO signal
        """
        passes, failures = self.check_liquidity(market_state)

        if passes:
            # Add limit price if not set
            if signal.limit_price is None:
                signal.limit_price = market_state.price

            return signal

        # Convert to NO_GO
        logger.info(
            "signal_converted_to_no_go",
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            reasons=failures,
        )

        return AlphaSignal(
            signal_id=signal.signal_id,
            action=SignalAction.NO_GO,
            ticker=signal.ticker,
            venue=signal.venue,
            confidence=0.0,
            reasoning=f"Liquidity guard rejection: {'; '.join(failures)}",
            valid_until=signal.valid_until,
            risk_flags=signal.risk_flags,
            source_paper_id=signal.source_paper_id,
            innovation_score=signal.innovation_score,
            sentiment_score=signal.sentiment_score,
        )
