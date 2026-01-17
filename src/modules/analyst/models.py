"""Data models for Analyst module (signal generation)."""

from pydantic import BaseModel, Field


class InnovationScore(BaseModel):
    """Result from innovation analysis."""

    score: float = Field(..., ge=-1.0, le=1.0, description="Innovation score")
    reasoning: str = Field(..., description="LLM reasoning")
    paper_id: str = Field(..., description="Source paper ID")
    ticker: str = Field(..., description="Analyzed ticker")


class SentimentScore(BaseModel):
    """Result from sentiment analysis."""

    score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score")
    hype_volume: float = Field(..., description="News volume Z-score")
    is_veto: bool = Field(default=False, description="Sentiment veto flag")
    ticker: str = Field(..., description="Analyzed ticker")
