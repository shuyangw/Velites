"""
The Sentiment Agent - FinBERT-based Guardrail

Prevents fighting the macro trend by analyzing news sentiment.
Acts as a veto mechanism when sentiment is deeply negative.
"""

import math
from datetime import UTC, datetime

from config import settings
from logging_config import get_logger
from modules.analyst.exceptions import SentimentError
from modules.analyst.models import SentimentScore
from modules.scout.models import NewsObject

logger = get_logger(__name__)

# Recency weighting decay factor (higher = faster decay)
RECENCY_DECAY_FACTOR = 0.1  # weight = exp(-0.1 * hours_old)


class SentimentEngine:
    """
    Sentiment analysis engine using FinBERT.

    Calculates weighted average sentiment of recent news and
    determines if a veto condition is met.
    """

    def __init__(self) -> None:
        self.model_name = settings.sentiment_model
        self.veto_threshold = settings.sentiment_veto_threshold
        self._model = None
        self._tokenizer = None

    def load_model(self) -> None:
        """Load the FinBERT model."""
        if self._model is not None:
            logger.debug("model_already_loaded")
            return

        logger.info("loading_sentiment_model", model=self.model_name)

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            raise SentimentError(
                "transformers and torch packages not installed. Run: pip install transformers torch"
            )

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)

            # Auto-detect device: GPU if available, else CPU
            import torch

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._model.to(self._device)
            self._model.eval()

            logger.info("model_loaded", device=str(self._device))
        except Exception as e:
            raise SentimentError(f"Failed to load sentiment model: {e}")

    async def analyze_sentiment(self, news_items: list[NewsObject], ticker: str) -> SentimentScore:
        """
        Analyze sentiment of news items for a ticker.

        Args:
            news_items: List of news articles to analyze
            ticker: Target ticker

        Returns:
            SentimentScore with aggregate sentiment and veto flag

        Logic:
            - Calculate weighted average sentiment of last 24h news
            - VETO Condition: If Sentiment < -0.6, block Long signals
        """
        if not news_items:
            logger.warning("no_news_items_for_sentiment", ticker=ticker)
            return SentimentScore(
                score=0.0,
                hype_volume=0.0,
                is_veto=False,
                ticker=ticker,
            )

        logger.info(
            "analyzing_sentiment",
            ticker=ticker,
            news_count=len(news_items),
        )

        # Ensure model is loaded
        self.load_model()

        # Current time for recency calculation
        now = datetime.now(UTC)

        # Calculate weighted sentiment
        total_weight = 0.0
        weighted_sum = 0.0

        headline_scores = []

        for news in news_items:
            # Calculate recency weight: exp(-decay * hours_old)
            if news.timestamp.tzinfo is None:
                # Assume UTC if no timezone
                news_time = news.timestamp.replace(tzinfo=UTC)
            else:
                news_time = news.timestamp

            hours_old = (now - news_time).total_seconds() / 3600
            hours_old = max(0, hours_old)  # Prevent negative values
            weight = math.exp(-RECENCY_DECAY_FACTOR * hours_old)

            # Analyze headline sentiment
            sentiment = self._analyze_single_headline(news.headline)

            headline_scores.append(
                {
                    "headline": news.headline[:80],
                    "sentiment": round(sentiment, 3),
                    "weight": round(weight, 3),
                    "hours_old": round(hours_old, 1),
                }
            )

            weighted_sum += sentiment * weight
            total_weight += weight

        # Log all headline scores (debug level)
        logger.debug(
            "sentiment_headline_scores",
            ticker=ticker,
            headline_count=len(headline_scores),
            scores=headline_scores,
        )

        # Calculate weighted average
        avg_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Calculate hype volume (Z-score of news count)
        hype_volume = self._calculate_hype_volume(len(news_items))

        # Check veto condition
        is_veto = self.should_veto(avg_score)

        # Log sentiment analysis result
        logger.info(
            "sentiment_analysis_complete",
            ticker=ticker,
            score=round(avg_score, 3),
            hype_volume=round(hype_volume, 2),
            news_count=len(news_items),
            is_veto=is_veto,
        )

        if is_veto:
            logger.warning(
                "sentiment_veto_triggered",
                ticker=ticker,
                score=avg_score,
                threshold=self.veto_threshold,
            )

        return SentimentScore(
            score=avg_score,
            hype_volume=hype_volume,
            is_veto=is_veto,
            ticker=ticker,
        )

    def _analyze_single_headline(self, headline: str) -> float:
        """
        Analyze sentiment of a single headline using FinBERT.

        Args:
            headline: News headline text

        Returns:
            Sentiment score from -1.0 (negative) to +1.0 (positive)
        """
        import torch
        import torch.nn.functional as F

        # Tokenize with truncation
        inputs = self._tokenizer(
            headline,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits

        # Apply softmax to get probabilities
        # FinBERT output order: negative (0), neutral (1), positive (2)
        probs = F.softmax(logits, dim=-1)[0]

        # Return P(positive) - P(negative)
        p_negative = probs[0].item()
        p_positive = probs[2].item()

        return p_positive - p_negative

    def _calculate_hype_volume(
        self, news_count: int, baseline: float = 5.0, std: float = 2.0
    ) -> float:
        """
        Calculate news volume Z-score.

        Args:
            news_count: Number of news items
            baseline: Expected baseline news count
            std: Standard deviation

        Returns:
            Z-score of news volume
        """
        return (news_count - baseline) / std

    def should_veto(self, sentiment_score: float) -> bool:
        """Check if sentiment triggers veto condition."""
        return sentiment_score < self.veto_threshold
