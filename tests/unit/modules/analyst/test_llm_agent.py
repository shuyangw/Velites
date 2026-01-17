"""Tests for LLM Agent."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.analyst.llm_agent import LLMAgent, MAX_RETRIES
from modules.analyst.exceptions import LLMError
from modules.analyst.models import InnovationScore


class TestLLMAgentInit:
    """Tests for LLMAgent initialization."""

    def test_init_loads_settings(self) -> None:
        """Test that LLMAgent loads settings correctly."""
        agent = LLMAgent()

        assert hasattr(agent, "provider")
        assert hasattr(agent, "model")
        assert hasattr(agent, "temperature")


class TestParseLLMResponse:
    """Tests for _parse_llm_response method."""

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON response."""
        agent = LLMAgent()

        content = '{"score": 0.85, "reasoning": "Major breakthrough in GPU architecture"}'
        result = agent._parse_llm_response(content, "NVDA", "arxiv_123")

        assert result.score == 0.85
        assert result.reasoning == "Major breakthrough in GPU architecture"
        assert result.ticker == "NVDA"
        assert result.paper_id == "arxiv_123"

    def test_parse_malformed_json_with_regex(self) -> None:
        """Test fallback to regex extraction for malformed JSON."""
        agent = LLMAgent()

        # JSON with extra text around it
        content = 'Here is my analysis: {"score": 0.7, "reasoning": "Notable advancement"} I hope this helps!'
        result = agent._parse_llm_response(content, "AMD", "arxiv_456")

        assert result.score == 0.7
        assert result.ticker == "AMD"

    def test_parse_unparseable_returns_neutral(self) -> None:
        """Test that unparseable content returns neutral score."""
        agent = LLMAgent()

        content = "This response has no valid JSON structure at all."
        result = agent._parse_llm_response(content, "INTC", "arxiv_789")

        assert result.score == 0.0
        assert "Failed to parse" in result.reasoning

    def test_parse_clamps_score_high(self) -> None:
        """Test that scores above 1.0 are clamped."""
        agent = LLMAgent()

        content = '{"score": 1.5, "reasoning": "Incredible breakthrough"}'
        result = agent._parse_llm_response(content, "NVDA", "arxiv_123")

        assert result.score == 1.0

    def test_parse_clamps_score_low(self) -> None:
        """Test that scores below -1.0 are clamped."""
        agent = LLMAgent()

        content = '{"score": -1.5, "reasoning": "Terrible news"}'
        result = agent._parse_llm_response(content, "NVDA", "arxiv_123")

        assert result.score == -1.0

    def test_parse_negative_score(self) -> None:
        """Test parsing negative scores."""
        agent = LLMAgent()

        content = '{"score": -0.6, "reasoning": "Competitive threat identified"}'
        result = agent._parse_llm_response(content, "NVDA", "arxiv_123")

        assert result.score == -0.6

    def test_parse_missing_reasoning(self) -> None:
        """Test parsing JSON with missing reasoning field."""
        agent = LLMAgent()

        content = '{"score": 0.5}'
        result = agent._parse_llm_response(content, "NVDA", "arxiv_123")

        assert result.score == 0.5
        assert result.reasoning == "No reasoning provided"


class TestGradeInnovation:
    """Tests for grade_innovation method."""

    def test_grade_innovation_unknown_provider(self) -> None:
        """Test that unknown provider raises LLMError."""
        agent = LLMAgent()
        agent.provider = "unknown"

        with pytest.raises(LLMError, match="Unknown LLM provider"):
            asyncio.get_event_loop().run_until_complete(
                agent.grade_innovation("test text", "NVDA", "GPU Designer")
            )

    def test_grade_innovation_routes_to_anthropic(self) -> None:
        """Test that anthropic provider routes correctly."""
        agent = LLMAgent()
        agent.provider = "anthropic"

        mock_score = InnovationScore(
            score=0.8,
            reasoning="Test",
            ticker="NVDA",
            paper_id="arxiv_123",
        )

        async def mock_call(*args, **kwargs):
            return mock_score

        agent._call_anthropic = mock_call

        result = asyncio.get_event_loop().run_until_complete(
            agent.grade_innovation("test abstract", "NVDA", "GPU Designer", "arxiv_123")
        )

        assert result == mock_score

    def test_grade_innovation_routes_to_openai(self) -> None:
        """Test that openai provider routes correctly."""
        agent = LLMAgent()
        agent.provider = "openai"

        mock_score = InnovationScore(
            score=0.6,
            reasoning="Test",
            ticker="AMD",
            paper_id="arxiv_456",
        )

        async def mock_call(*args, **kwargs):
            return mock_score

        agent._call_openai = mock_call

        result = asyncio.get_event_loop().run_until_complete(
            agent.grade_innovation("test abstract", "AMD", "CPU Designer", "arxiv_456")
        )

        assert result == mock_score


class TestCallAnthropicMissingKey:
    """Tests for Anthropic API without key."""

    def test_call_anthropic_missing_key(self) -> None:
        """Test that missing API key raises LLMError."""
        agent = LLMAgent()

        # Temporarily clear the API key
        import config
        original_key = getattr(config.settings, 'anthropic_api_key', None)
        config.settings.anthropic_api_key = None

        try:
            with pytest.raises(LLMError, match="ANTHROPIC_API_KEY not configured"):
                asyncio.get_event_loop().run_until_complete(
                    agent._call_anthropic("test prompt", "NVDA", "arxiv_123")
                )
        finally:
            # Restore the key
            config.settings.anthropic_api_key = original_key


class TestCallOpenAIMissingKey:
    """Tests for OpenAI API without key."""

    def test_call_openai_missing_key_or_package(self) -> None:
        """Test that missing API key or missing package raises LLMError."""
        agent = LLMAgent()

        # Check if openai package is installed
        try:
            import openai
            openai_installed = True
        except ImportError:
            openai_installed = False

        import config
        original_key = getattr(config.settings, 'openai_api_key', None)
        config.settings.openai_api_key = None

        try:
            # Either "not configured" (if package installed) or "not installed"
            with pytest.raises(LLMError):
                asyncio.get_event_loop().run_until_complete(
                    agent._call_openai("test prompt", "NVDA", "arxiv_123")
                )
        finally:
            # Restore the key
            config.settings.openai_api_key = original_key
