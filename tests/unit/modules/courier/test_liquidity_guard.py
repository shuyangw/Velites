"""Tests for Liquidity Guard."""

import pytest

from velites.modules.courier.liquidity_guard import LiquidityGuard
from velites.models.market import LiquidityStatus, MarketState
from velites.models.signal import AlphaSignal, SignalAction


class TestLiquidityGuard:
    """Tests for LiquidityGuard class."""

    def test_check_liquidity_passes(self, sample_market_state: MarketState) -> None:
        """Test liquidity check passes for liquid stock."""
        guard = LiquidityGuard()

        passes, failures = guard.check_liquidity(sample_market_state)

        assert passes is True
        assert len(failures) == 0

    def test_check_liquidity_fails_high_spread(self) -> None:
        """Test liquidity check fails for high spread."""
        guard = LiquidityGuard()

        illiquid_state = MarketState(
            ticker="SSNLF",
            price=50.0,
            volume_30d_avg=100_000,
            spread_pct=3.5,  # Above 2% threshold
            liquidity_status=LiquidityStatus.LOW,
        )

        passes, failures = guard.check_liquidity(illiquid_state)

        assert passes is False
        assert any("spread" in f.lower() for f in failures)

    def test_check_liquidity_fails_low_volume(self) -> None:
        """Test liquidity check fails for low volume."""
        guard = LiquidityGuard()

        low_volume_state = MarketState(
            ticker="SMALL",
            price=10.0,
            volume_30d_avg=10_000,  # 10k * $10 = $100k < $500k
            spread_pct=0.5,
            liquidity_status=LiquidityStatus.LOW,
        )

        passes, failures = guard.check_liquidity(low_volume_state)

        assert passes is False
        assert any("volume" in f.lower() for f in failures)

    def test_validate_signal_converts_to_no_go(
        self, sample_market_state: MarketState
    ) -> None:
        """Test that failing liquidity converts signal to NO_GO."""
        guard = LiquidityGuard()

        # Create illiquid market state
        illiquid_state = sample_market_state.model_copy()
        illiquid_state.spread_pct = 5.0

        # Create a BUY signal
        from datetime import datetime, timedelta

        signal = AlphaSignal(
            signal_id="test_001",
            action=SignalAction.BUY_LONG,
            ticker="TEST",
            confidence=0.9,
            reasoning="Test signal",
            valid_until=datetime.utcnow() + timedelta(hours=24),
        )

        result = guard.validate_signal(signal, illiquid_state)

        assert result.action == SignalAction.NO_GO
        assert "liquidity" in result.reasoning.lower()
