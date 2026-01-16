"""
The Confluence Engine - Final Decision Matrix

Combines innovation and sentiment scores with time-lag logic
and hype filtering to produce final trading signals.
"""

from datetime import datetime, timedelta
import uuid

from velites.logging import get_logger
from velites.modules.mapper.models import RiskFlag
from velites.modules.analyst.models import InnovationScore, SentimentScore
from velites.modules.courier.models import AlphaSignal, SignalAction

logger = get_logger(__name__)


class ConfluenceEngine:
    """
    Final decision engine that combines all signals.

    Applies:
    - Innovation + Sentiment combination
    - Time-Lag Logic: ArXiv (Leading) + News Quiet (Lagging) = High Confidence
    - Hype Filter: News Volume > 3σ = Hold/Wait (Too crowded)
    """

    # Thresholds
    INNOVATION_THRESHOLD = 0.7
    SENTIMENT_VETO_THRESHOLD = -0.5
    HYPE_THRESHOLD = 3.0  # Standard deviations

    def __init__(self) -> None:
        pass

    def generate_signal(
        self,
        ticker: str,
        innovation: InnovationScore,
        sentiment: SentimentScore,
        source_type: str = "arxiv",
        risk_flags: list[RiskFlag] | None = None,
    ) -> AlphaSignal:
        """
        Generate final trading signal from combined analysis.

        Args:
            ticker: Target ticker
            innovation: Innovation score from LLM agent
            sentiment: Sentiment score from FinBERT
            source_type: Source of the signal (arxiv, patent, news)
            risk_flags: Pre-existing risk flags

        Returns:
            AlphaSignal with action and confidence

        Logic:
            - IF Innovation > 0.7 AND Sentiment > -0.5 THEN SIGNAL = TRUE
            - IF Source is ArXiv AND News is Quiet -> High Confidence
            - IF News Volume > 3σ -> Hold/Wait
        """
        risk_flags = risk_flags or []

        logger.info(
            "generating_confluence_signal",
            ticker=ticker,
            innovation_score=innovation.score,
            sentiment_score=sentiment.score,
            hype_volume=sentiment.hype_volume,
        )

        # Check veto conditions
        if sentiment.is_veto or sentiment.score < self.SENTIMENT_VETO_THRESHOLD:
            logger.info("signal_vetoed_by_sentiment", ticker=ticker)
            return self._create_signal(
                ticker=ticker,
                action=SignalAction.IGNORE,
                confidence=0.0,
                reasoning="Sentiment veto: macro trend is deeply negative",
                innovation=innovation,
                sentiment=sentiment,
                risk_flags=risk_flags,
            )

        # Check hype filter
        if sentiment.hype_volume > self.HYPE_THRESHOLD:
            logger.info("signal_held_due_to_hype", ticker=ticker)
            return self._create_signal(
                ticker=ticker,
                action=SignalAction.WAIT,
                confidence=0.3,
                reasoning=f"Hype filter: news volume {sentiment.hype_volume:.1f}σ above normal",
                innovation=innovation,
                sentiment=sentiment,
                risk_flags=risk_flags,
            )

        # Check innovation threshold
        if innovation.score < self.INNOVATION_THRESHOLD:
            logger.info("signal_ignored_low_innovation", ticker=ticker)
            return self._create_signal(
                ticker=ticker,
                action=SignalAction.IGNORE,
                confidence=0.2,
                reasoning="Innovation score below threshold",
                innovation=innovation,
                sentiment=sentiment,
                risk_flags=risk_flags,
            )

        # Calculate confidence with time-lag bonus
        confidence = self._calculate_confidence(innovation, sentiment, source_type)

        return self._create_signal(
            ticker=ticker,
            action=SignalAction.BUY_LONG,
            confidence=confidence,
            reasoning=f"{innovation.reasoning} Market sentiment is {'quiet' if sentiment.hype_volume < 1 else 'moderate'}.",
            innovation=innovation,
            sentiment=sentiment,
            risk_flags=risk_flags,
        )

    def _calculate_confidence(
        self,
        innovation: InnovationScore,
        sentiment: SentimentScore,
        source_type: str,
    ) -> float:
        """Calculate final confidence score with time-lag bonus."""
        base_confidence = (innovation.score + 1) / 2  # Normalize to 0-1

        # Time-lag bonus: ArXiv (leading) + quiet news (lagging) = higher confidence
        if source_type == "arxiv" and sentiment.hype_volume < 1.0:
            base_confidence *= 1.2

        # Sentiment modifier
        if sentiment.score > 0:
            base_confidence *= 1 + (sentiment.score * 0.1)

        return min(base_confidence, 1.0)

    def _create_signal(
        self,
        ticker: str,
        action: SignalAction,
        confidence: float,
        reasoning: str,
        innovation: InnovationScore,
        sentiment: SentimentScore,
        risk_flags: list[RiskFlag],
    ) -> AlphaSignal:
        """Create an AlphaSignal instance."""
        return AlphaSignal(
            signal_id=f"velites_{uuid.uuid4().hex[:8]}",
            action=action,
            ticker=ticker,
            confidence=confidence,
            reasoning=reasoning,
            valid_until=datetime.utcnow() + timedelta(hours=24),
            risk_flags=risk_flags,
            source_paper_id=innovation.paper_id,
            innovation_score=innovation.score,
            sentiment_score=sentiment.score,
        )
