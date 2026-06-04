"""Tests for Sentiment Engine."""

import asyncio
import math
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from modules.analyst.models import SentimentScore
from modules.analyst.sentiment_engine import (
    RECENCY_DECAY_FACTOR,
    SentimentEngine,
)
from modules.scout.models import NewsObject


class TestSentimentEngineInit:
    """Tests for SentimentEngine initialization."""

    def test_init_loads_settings(self) -> None:
        """Test that SentimentEngine loads settings correctly."""
        engine = SentimentEngine()

        assert hasattr(engine, "model_name")
        assert hasattr(engine, "veto_threshold")
        assert engine._model is None
        assert engine._tokenizer is None


class TestCalculateHypeVolume:
    """Tests for _calculate_hype_volume method."""

    def test_calculate_hype_volume_baseline(self) -> None:
        """Test Z-score at baseline returns 0."""
        engine = SentimentEngine()

        z_score = engine._calculate_hype_volume(5, baseline=5.0, std=2.0)

        assert z_score == 0.0

    def test_calculate_hype_volume_above_baseline(self) -> None:
        """Test Z-score above baseline is positive."""
        engine = SentimentEngine()

        z_score = engine._calculate_hype_volume(9, baseline=5.0, std=2.0)

        assert z_score == 2.0  # (9 - 5) / 2

    def test_calculate_hype_volume_below_baseline(self) -> None:
        """Test Z-score below baseline is negative."""
        engine = SentimentEngine()

        z_score = engine._calculate_hype_volume(1, baseline=5.0, std=2.0)

        assert z_score == -2.0  # (1 - 5) / 2


class TestShouldVeto:
    """Tests for should_veto method."""

    def test_should_veto_below_threshold(self) -> None:
        """Test veto triggers below threshold."""
        engine = SentimentEngine()
        engine.veto_threshold = -0.6

        assert engine.should_veto(-0.7) is True
        assert engine.should_veto(-0.61) is True

    def test_should_veto_above_threshold(self) -> None:
        """Test no veto above threshold."""
        engine = SentimentEngine()
        engine.veto_threshold = -0.6

        assert engine.should_veto(-0.5) is False
        assert engine.should_veto(0.0) is False
        assert engine.should_veto(0.5) is False

    def test_should_veto_at_threshold(self) -> None:
        """Test no veto exactly at threshold."""
        engine = SentimentEngine()
        engine.veto_threshold = -0.6

        assert engine.should_veto(-0.6) is False


class TestRecencyWeighting:
    """Tests for recency weighting logic."""

    def test_recency_weight_recent(self) -> None:
        """Test that recent news has weight close to 1.0."""
        hours_old = 0
        weight = math.exp(-RECENCY_DECAY_FACTOR * hours_old)

        assert weight == 1.0

    def test_recency_weight_1_hour(self) -> None:
        """Test weight decay after 1 hour."""
        hours_old = 1
        weight = math.exp(-RECENCY_DECAY_FACTOR * hours_old)

        # exp(-0.1 * 1) approx 0.905
        assert 0.90 < weight < 0.91

    def test_recency_weight_24_hours(self) -> None:
        """Test weight decay after 24 hours."""
        hours_old = 24
        weight = math.exp(-RECENCY_DECAY_FACTOR * hours_old)

        # exp(-0.1 * 24) approx 0.091
        assert 0.08 < weight < 0.10

    def test_recency_weight_48_hours(self) -> None:
        """Test weight decay after 48 hours."""
        hours_old = 48
        weight = math.exp(-RECENCY_DECAY_FACTOR * hours_old)

        # exp(-0.1 * 48) approx 0.0082
        assert weight < 0.01


class TestLoadModel:
    """Tests for load_model method."""

    def test_load_model_caches_model(self) -> None:
        """Test that model is cached after first load."""
        engine = SentimentEngine()

        # Pre-populate to simulate already loaded
        engine._model = MagicMock()
        engine._tokenizer = MagicMock()

        # Should not raise or reload
        engine.load_model()

        # Model should still be the same mock
        assert engine._model is not None


class TestAnalyzeSentiment:
    """Tests for analyze_sentiment method."""

    @pytest.fixture
    def sample_news_items(self) -> list[NewsObject]:
        """Create sample news items for testing."""
        now = datetime.now(UTC)
        return [
            NewsObject(
                id="news_1",
                headline="NVIDIA Reports Record Revenue Growth",
                summary="Strong earnings beat expectations...",
                source="Test Feed",
                url="https://example.com/1",
                timestamp=now - timedelta(hours=1),
                tickers=["NVDA"],
                keywords=["revenue", "growth"],
            ),
            NewsObject(
                id="news_2",
                headline="Tech Sector Faces Headwinds",
                summary="Concerns about interest rates...",
                source="Test Feed",
                url="https://example.com/2",
                timestamp=now - timedelta(hours=6),
                tickers=["NVDA"],
                keywords=["headwinds"],
            ),
        ]

    def test_analyze_sentiment_empty_news(self) -> None:
        """Test neutral score for empty news list."""
        engine = SentimentEngine()

        result = asyncio.get_event_loop().run_until_complete(engine.analyze_sentiment([], "NVDA"))

        assert isinstance(result, SentimentScore)
        assert result.score == 0.0
        assert result.hype_volume == 0.0
        assert result.is_veto is False
        assert result.ticker == "NVDA"

    def test_analyze_sentiment_with_mocked_model(self, sample_news_items: list[NewsObject]) -> None:
        """Test sentiment analysis with mocked _analyze_single_headline."""
        engine = SentimentEngine()

        # Mock the model components to avoid loading real model
        engine._model = MagicMock()
        engine._tokenizer = MagicMock()
        engine._device = "cpu"

        # Mock _analyze_single_headline to return consistent values
        original_analyze = engine._analyze_single_headline
        engine._analyze_single_headline = MagicMock(return_value=0.5)

        try:
            result = asyncio.get_event_loop().run_until_complete(
                engine.analyze_sentiment(sample_news_items, "NVDA")
            )

            assert isinstance(result, SentimentScore)
            assert result.ticker == "NVDA"
            # Two news items, both positive, should result in positive score
            assert result.score > 0
        finally:
            engine._analyze_single_headline = original_analyze

    def test_analyze_sentiment_veto_triggered(self) -> None:
        """Test that veto is triggered on deeply negative sentiment."""
        engine = SentimentEngine()
        engine.veto_threshold = -0.6

        now = datetime.now(UTC)
        negative_news = [
            NewsObject(
                id="news_1",
                headline="Major Lawsuit Filed Against Company",
                summary="Legal troubles mount...",
                source="Test Feed",
                url="https://example.com/1",
                timestamp=now - timedelta(hours=1),
                tickers=["NVDA"],
                keywords=["lawsuit"],
            ),
        ]

        # Mock model and return negative sentiment
        engine._model = MagicMock()
        engine._tokenizer = MagicMock()
        engine._device = "cpu"
        engine._analyze_single_headline = MagicMock(return_value=-0.8)

        result = asyncio.get_event_loop().run_until_complete(
            engine.analyze_sentiment(negative_news, "NVDA")
        )

        assert result.is_veto is True
        assert result.score < engine.veto_threshold


class TestAnalyzeSingleHeadline:
    """Tests for _analyze_single_headline method."""

    def test_analyze_single_headline_requires_model(self) -> None:
        """Test that _analyze_single_headline requires loaded model."""
        engine = SentimentEngine()
        engine._model = None

        # Should raise AttributeError since model is None
        with pytest.raises((AttributeError, TypeError)):
            engine._analyze_single_headline("Test headline")

    def test_analyze_single_headline_with_mock(self) -> None:
        """Test headline analysis with mocked model."""
        import torch

        engine = SentimentEngine()

        # Create mock tokenizer that returns tensors
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]]),
        }

        # Create mock model
        mock_model = MagicMock()
        # FinBERT output: [batch, 3] -> [negative, neutral, positive]
        mock_logits = torch.tensor([[0.1, 0.2, 0.7]])  # Positive sentiment
        mock_outputs = MagicMock()
        mock_outputs.logits = mock_logits
        mock_model.return_value = mock_outputs

        engine._model = mock_model
        engine._tokenizer = mock_tokenizer
        engine._device = "cpu"

        result = engine._analyze_single_headline("NVIDIA beats earnings expectations")

        # P(positive) - P(negative) should be positive
        assert result > 0


class TestIntegration:
    """Integration tests (require actual model, skipped by default)."""

    @pytest.mark.skip(reason="Requires FinBERT model download")
    def test_full_sentiment_pipeline(self) -> None:
        """Test full sentiment analysis pipeline with real model."""
        engine = SentimentEngine()
        engine.load_model()

        now = datetime.now(UTC)
        news = [
            NewsObject(
                id="news_1",
                headline="Company Reports Strong Quarterly Earnings",
                summary="Revenue up 50%...",
                source="Test",
                url="https://example.com",
                timestamp=now,
                tickers=["TEST"],
                keywords=[],
            ),
        ]

        result = asyncio.get_event_loop().run_until_complete(engine.analyze_sentiment(news, "TEST"))

        # Should be positive sentiment
        assert result.score > 0
