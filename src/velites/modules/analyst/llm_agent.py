"""
The Innovation Agent - LLM-based Analysis

Rates the significance of technical findings using GPT-4o or Claude.
"""

from abc import ABC, abstractmethod

from velites.config import settings
from velites.logging import get_logger
from velites.modules.analyst.exceptions import LLMError
from velites.modules.analyst.models import InnovationScore

logger = get_logger(__name__)


INNOVATION_PROMPT = """You are a semiconductor industry analyst. Analyze the following technical paper abstract and determine if it describes a material breakthrough for {ticker}.

Context about {ticker}: {ticker_context}

Paper Abstract:
{abstract}

Rate the innovation significance from -1.0 to +1.0 where:
- +1.0: Major breakthrough that could significantly impact the company's competitive position
- +0.5: Notable advancement with moderate business impact
- 0.0: Incremental improvement or neutral
- -0.5: Potential negative impact or competitive threat
- -1.0: Major threat to the company's market position

Respond with a JSON object:
{{"score": <float>, "reasoning": "<your analysis>"}}
"""


class BaseLLMAgent(ABC):
    """Abstract base class for LLM agents."""

    @abstractmethod
    async def grade_innovation(
        self, text: str, ticker: str, ticker_context: str
    ) -> InnovationScore:
        """Grade the innovation significance of text for a ticker."""
        pass


class LLMAgent(BaseLLMAgent):
    """LLM agent for innovation analysis using OpenAI or Anthropic."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature

    async def grade_innovation(
        self,
        text: str,
        ticker: str,
        ticker_context: str,
        paper_id: str = "unknown",
    ) -> InnovationScore:
        """
        Rate the significance of a technical finding.

        Args:
            text: Paper abstract or technical text
            ticker: Target ticker being analyzed
            ticker_context: Context about the ticker (e.g., "NVDA is a GPU Designer")
            paper_id: Source paper ID for tracking

        Returns:
            InnovationScore with rating and reasoning

        Example:
            >>> await agent.grade_innovation(abstract, "NVDA", "GPU Designer")
            InnovationScore(score=0.85, reasoning="Novel architecture...", ...)
        """
        logger.info(
            "grading_innovation",
            ticker=ticker,
            provider=self.provider,
            model=self.model,
        )

        prompt = INNOVATION_PROMPT.format(
            ticker=ticker,
            ticker_context=ticker_context,
            abstract=text,
        )

        if self.provider == "openai":
            return await self._call_openai(prompt, ticker, paper_id)
        elif self.provider == "anthropic":
            return await self._call_anthropic(prompt, ticker, paper_id)
        else:
            raise LLMError(f"Unknown LLM provider: {self.provider}")

    async def _call_openai(
        self, prompt: str, ticker: str, paper_id: str
    ) -> InnovationScore:
        """Call OpenAI API."""
        # TODO: Implement OpenAI API call
        # from openai import AsyncOpenAI
        # client = AsyncOpenAI(api_key=settings.openai_api_key)
        raise NotImplementedError("OpenAI integration not yet implemented")

    async def _call_anthropic(
        self, prompt: str, ticker: str, paper_id: str
    ) -> InnovationScore:
        """Call Anthropic API."""
        # TODO: Implement Anthropic API call
        # from anthropic import AsyncAnthropic
        # client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        raise NotImplementedError("Anthropic integration not yet implemented")
