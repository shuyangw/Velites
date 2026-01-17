# Analyst Module Architecture

The Analyst module is Velites' signal generation layer, using LLMs and sentiment models to score innovation relevance and market sentiment.

## Purpose

Analyst transforms raw data into actionable scores:
- **Innovation scoring** - LLM grades paper relevance to specific tickers
- **Sentiment analysis** - FinBERT analyzes news headline sentiment
- Combined scores inform trading decisions

## Component Diagram

```
                    +-------------------+
                    |  ANALYST MODULE   |
                    +-------------------+
                            |
            +---------------+---------------+
            |                               |
            v                               v
    +---------------+               +---------------+
    |   LLMAgent    |               |SentimentEngine|
    +---------------+               +---------------+
            |                               |
    +-------+-------+                       |
    |               |                       v
    v               v                   FinBERT
 Anthropic      OpenAI              (ProsusAI/finbert)
   API           API
```

## Components

### LLMAgent (`llm_agent.py`)

Grades academic papers for innovation relevance to specific tickers.

**Key Methods:**
- `grade_innovation(abstract, ticker, role, paper_id)` - Main entry
- `_call_anthropic(prompt, ticker, paper_id)` - Anthropic API
- `_call_openai(prompt, ticker, paper_id)` - OpenAI API
- `_parse_llm_response(content, ticker, paper_id)` - JSON parser

**Prompt Structure:**
```
You are a {role} at {ticker}'s R&D department.

Analyze this research paper abstract and score its relevance:
- Score from -1.0 (threat) to +1.0 (opportunity)
- Consider competitive implications
- Focus on near-term (6-12 month) impact

Abstract: {abstract}

Respond in JSON: {"score": float, "reasoning": string}
```

**Retry Logic:**
- 3 attempts with exponential backoff (2s, 4s, 8s)
- Handles rate limits and transient errors

**Configuration:**
```python
settings.llm_provider      # "anthropic" or "openai"
settings.llm_model         # e.g., "claude-sonnet-4-5-20250929"
settings.llm_temperature   # 0.1 (low creativity)
settings.anthropic_api_key
settings.openai_api_key
```

### SentimentEngine (`sentiment_engine.py`)

Analyzes news sentiment using FinBERT financial sentiment model.

**Key Methods:**
- `load_model()` - Load FinBERT (lazy, cached)
- `analyze_sentiment(news_items, ticker)` - Aggregate sentiment
- `_analyze_single_headline(headline)` - Single headline score

**Sentiment Calculation:**
```python
# FinBERT returns: [P(positive), P(negative), P(neutral)]
# Sentiment score = P(positive) - P(negative)
# Range: -1.0 (negative) to +1.0 (positive)
```

**Recency Weighting:**
```python
# Recent news weighted more heavily
hours_old = (now - news.timestamp).total_seconds() / 3600
weight = exp(-0.1 * hours_old)

# 0 hours old  -> weight = 1.0
# 7 hours old  -> weight = 0.5
# 24 hours old -> weight = 0.09
```

**Configuration:**
```python
settings.sentiment_model         # "ProsusAI/finbert"
settings.sentiment_veto_threshold  # -0.6 (veto if below)
```

## Data Models

### InnovationScore
```python
class InnovationScore(BaseModel):
    score: float        # -1.0 to +1.0
    reasoning: str      # LLM explanation
    ticker: str         # Target ticker
    paper_id: str       # Source paper ID
```

### SentimentResult
```python
class SentimentResult(BaseModel):
    score: float              # -1.0 to +1.0 (weighted average)
    headline_count: int       # Number of headlines analyzed
    ticker: str               # Target ticker
    dominant_sentiment: str   # "positive", "negative", "neutral"
```

## Scoring Pipeline

```
ArXiv Paper Abstract
        |
        v
+------------------+
|    LLMAgent      |
| grade_innovation |
+------------------+
        |
        v
InnovationScore (-1.0 to +1.0)
        |
        +----------------------+
        |                      |
        v                      v
   score > 0.3?          score < -0.3?
        |                      |
   OPPORTUNITY              THREAT
        |                      |
        v                      v
+------------------+    Signal: IGNORE
| SentimentEngine  |
|analyze_sentiment |
+------------------+
        |
        v
SentimentResult
        |
        v
   sentiment > -0.6?
        |
   +----+----+
   |         |
  YES        NO
   |         |
   v         v
PROCEED    VETO
```

## Error Handling

```python
class LLMError(VelitesError):
    """Raised when LLM call fails."""
    pass

class SentimentError(VelitesError):
    """Raised when sentiment analysis fails."""
    pass
```

Common scenarios:
- API key not configured
- Rate limit exceeded
- Malformed LLM response
- Model loading failure

## Response Parsing

LLM responses are parsed with fallbacks:

1. **JSON parsing** - Try `json.loads()`
2. **Regex extraction** - Find `{"score": X, "reasoning": "..."}` pattern
3. **Default** - Return neutral score (0.0) with error message

Score clamping ensures valid range:
```python
score = max(-1.0, min(1.0, raw_score))
```

## Model Caching

FinBERT is loaded once and cached:
```python
_model_cache: dict[str, tuple[AutoModelForSequenceClassification, AutoTokenizer]] = {}

def load_model(self):
    if self.model_name in _model_cache:
        return _model_cache[self.model_name]
    # Load and cache...
```

## File Structure

```
src/modules/analyst/
    __init__.py
    llm_agent.py
    sentiment_engine.py
    models.py
    exceptions.py
```
