"""
The Innovation Agent - LLM-based Analysis

Rates the significance of technical findings using GPT-4o or Claude.
"""

import asyncio
import json
import re
from abc import ABC, abstractmethod

from config import settings
from logging_config import get_logger
from modules.analyst.exceptions import LLMError
from modules.analyst.models import InnovationScore

logger = get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


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
        """Call OpenAI API with retry logic."""
        try:
            from openai import AsyncOpenAI, RateLimitError, APIConnectionError
        except ImportError:
            raise LLMError("openai package not installed. Run: pip install openai")

        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY not configured")

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.choices[0].message.content
                return self._parse_llm_response(content, ticker, paper_id)

            except RateLimitError as e:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "openai_rate_limit",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"OpenAI rate limit exceeded after {MAX_RETRIES} retries")

            except APIConnectionError as e:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "openai_connection_error",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"OpenAI connection failed after {MAX_RETRIES} retries: {e}")

            except Exception as e:
                raise LLMError(f"OpenAI API error: {e}")

        raise LLMError("OpenAI call failed unexpectedly")

    async def _call_anthropic(
        self, prompt: str, ticker: str, paper_id: str
    ) -> InnovationScore:
        """Call Anthropic API with retry logic."""
        try:
            from anthropic import AsyncAnthropic, RateLimitError, APIConnectionError
        except ImportError:
            raise LLMError("anthropic package not installed. Run: pip install anthropic")

        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY not configured")

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text
                return self._parse_llm_response(content, ticker, paper_id)

            except RateLimitError as e:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "anthropic_rate_limit",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"Anthropic rate limit exceeded after {MAX_RETRIES} retries")

            except APIConnectionError as e:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "anthropic_connection_error",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"Anthropic connection failed after {MAX_RETRIES} retries: {e}")

            except Exception as e:
                raise LLMError(f"Anthropic API error: {e}")

        raise LLMError("Anthropic call failed unexpectedly")

    def _parse_llm_response(
        self, content: str, ticker: str, paper_id: str
    ) -> InnovationScore:
        """
        Parse LLM response JSON into InnovationScore.

        Handles malformed JSON with regex fallback.
        """
        # Try direct JSON parsing first
        try:
            data = json.loads(content)
            score = float(data.get("score", 0.0))
            reasoning = data.get("reasoning", "No reasoning provided")
        except (json.JSONDecodeError, ValueError):
            # Fallback: regex extraction for malformed JSON
            logger.warning("json_parse_failed", content=content[:200])

            score_match = re.search(r'"score"\s*:\s*(-?[\d.]+)', content)
            reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', content)

            if score_match:
                try:
                    score = float(score_match.group(1))
                    reasoning = reasoning_match.group(1) if reasoning_match else "Extracted via regex"
                except ValueError:
                    score = 0.0
                    reasoning = "Failed to parse LLM response"
            else:
                # Final fallback: neutral score
                logger.error("llm_response_unparseable", content=content[:500])
                score = 0.0
                reasoning = "Failed to parse LLM response"

        # Clamp score to valid range
        score = max(-1.0, min(1.0, score))

        return InnovationScore(
            score=score,
            reasoning=reasoning,
            ticker=ticker,
            paper_id=paper_id,
        )
