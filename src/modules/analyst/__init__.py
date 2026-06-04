"""
Analyst Module - Signal Generation

The "Processor" of Velites. Interprets data significance using AI.

Components:
- Innovation Agent (llm_agent): Rates technical finding significance
- Sentiment Agent (sentiment_engine): Prevents fighting macro trends
- Confluence Engine (confluence): Final decision matrix
"""

from modules.analyst.confluence import ConfluenceEngine
from modules.analyst.llm_agent import LLMAgent
from modules.analyst.sentiment_engine import SentimentEngine

__all__ = ["LLMAgent", "SentimentEngine", "ConfluenceEngine"]
