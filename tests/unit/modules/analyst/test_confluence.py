"""Tests for Confluence Engine."""

import pytest

from modules.analyst.confluence import ConfluenceEngine
from modules.analyst.models import InnovationScore, SentimentScore
from modules.courier.models import SignalAction


class TestConfluenceEngine:
    """Tests for ConfluenceEngine class."""

    def test_generate_signal_buy(
        self, sample_innovation_score: InnovationScore, sample_sentiment_score: SentimentScore
    ) -> None:
        """Test BUY signal generation with good scores."""
        engine = ConfluenceEngine()

        signal = engine.generate_signal(
            ticker="NVDA",
            innovation=sample_innovation_score,
            sentiment=sample_sentiment_score,
        )

        assert signal.action == SignalAction.BUY_LONG
        assert signal.ticker == "NVDA"
        assert signal.confidence > 0.5

    def test_generate_signal_veto_on_negative_sentiment(
        self, sample_innovation_score: InnovationScore
    ) -> None:
        """Test signal veto on deeply negative sentiment."""
        engine = ConfluenceEngine()

        negative_sentiment = SentimentScore(
            score=-0.7,
            hype_volume=1.0,
            is_veto=True,
            ticker="NVDA",
        )

        signal = engine.generate_signal(
            ticker="NVDA",
            innovation=sample_innovation_score,
            sentiment=negative_sentiment,
        )

        assert signal.action == SignalAction.IGNORE
        assert "veto" in signal.reasoning.lower()

    def test_generate_signal_wait_on_high_hype(
        self, sample_innovation_score: InnovationScore
    ) -> None:
        """Test WAIT signal on high news volume (hype)."""
        engine = ConfluenceEngine()

        high_hype_sentiment = SentimentScore(
            score=0.3,
            hype_volume=4.0,  # Above 3σ threshold
            is_veto=False,
            ticker="NVDA",
        )

        signal = engine.generate_signal(
            ticker="NVDA",
            innovation=sample_innovation_score,
            sentiment=high_hype_sentiment,
        )

        assert signal.action == SignalAction.WAIT
        assert "hype" in signal.reasoning.lower()

    def test_generate_signal_ignore_low_innovation(
        self, sample_sentiment_score: SentimentScore
    ) -> None:
        """Test IGNORE signal on low innovation score."""
        engine = ConfluenceEngine()

        low_innovation = InnovationScore(
            score=0.3,  # Below 0.7 threshold
            reasoning="Minor incremental improvement",
            paper_id="arxiv_123",
            ticker="NVDA",
        )

        signal = engine.generate_signal(
            ticker="NVDA",
            innovation=low_innovation,
            sentiment=sample_sentiment_score,
        )

        assert signal.action == SignalAction.IGNORE

    def test_time_lag_bonus_arxiv_quiet_news(
        self, sample_innovation_score: InnovationScore
    ) -> None:
        """Test confidence boost for ArXiv + quiet news combination."""
        engine = ConfluenceEngine()

        quiet_sentiment = SentimentScore(
            score=0.1,
            hype_volume=0.3,  # Very quiet
            is_veto=False,
            ticker="NVDA",
        )

        signal_arxiv = engine.generate_signal(
            ticker="NVDA",
            innovation=sample_innovation_score,
            sentiment=quiet_sentiment,
            source_type="arxiv",
        )

        signal_news = engine.generate_signal(
            ticker="NVDA",
            innovation=sample_innovation_score,
            sentiment=quiet_sentiment,
            source_type="news",
        )

        # ArXiv source should have higher confidence due to time-lag bonus
        assert signal_arxiv.confidence >= signal_news.confidence
