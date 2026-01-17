# Scout Module Architecture

The Scout module is Velites' data acquisition layer, responsible for fetching academic papers, business news, and market data.

## Purpose

Scout provides the raw inputs for the analysis pipeline:
- **ArXiv papers** - Academic research that may signal innovation
- **News articles** - Business context and sentiment signals
- **Market data** - Current prices, volume, and liquidity metrics

## Component Diagram

```
                    +-------------------+
                    |   SCOUT MODULE    |
                    +-------------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
+---------------+   +---------------+   +---------------+
| ArxivFetcher  |   | NewsFetcher   |   | MarketFetcher |
+---------------+   +---------------+   +---------------+
        |                   |                   |
        v                   v                   v
   ArXiv API           Tiingo API          yfinance/
   (feedparser)        RSS Feeds           Alpaca API
```

## Components

### ArxivFetcher (`arxiv_fetcher.py`)

Fetches academic papers from ArXiv RSS feeds.

**Key Methods:**
- `fetch_papers(categories, lookback_hours)` - Fetch recent papers
- `_parse_entry(entry)` - Parse RSS entry to ArxivPaper model

**Configuration:**
```python
settings.arxiv_categories  # ["cs.AI", "cs.LG", "cs.AR", "cs.CV"]
settings.arxiv_max_results # 100
settings.arxiv_lookback_hours # 24
```

**Output:** `list[ArxivPaper]`

### NewsFetcher (`news_fetcher.py`)

Aggregates news from multiple sources with supply chain keyword filtering.

**Key Methods:**
- `fetch_news(tickers, keywords, lookback_hours)` - Main entry point
- `fetch_from_tiingo(tickers, start_date)` - Tiingo API
- `fetch_from_rss(feed_urls)` - RSS feeds fallback

**Supply Chain Keywords:**
```python
SUPPLY_CHAIN_KEYWORDS = [
    "capacity", "yield", "shortage", "delay",
    "production", "manufacturing", "supply",
    "demand", "inventory", "backlog"
]
```

**Configuration:**
```python
settings.tiingo_api_key    # Primary news source
settings.newsdata_api_key  # Secondary source
```

**Output:** `list[NewsObject]`

### MarketFetcher (`market_fetcher.py`)

Provides current market state for liquidity validation.

**Key Methods:**
- `fetch_market_state(ticker)` - Single ticker
- `fetch_batch_market_state(tickers)` - Multiple tickers
- `_fetch_from_yfinance(ticker)` - Development provider
- `_fetch_from_alpaca(ticker)` - Production provider
- `_classify_liquidity(volume, spread)` - Liquidity classification

**Liquidity Classification:**
```
HIGH:     volume >= 1M AND spread <= 0.5%
MEDIUM:   volume >= 500K AND spread <= 1.0%
LOW:      volume >= 100K AND spread <= 2.0%
ILLIQUID: volume < 100K OR spread > 2.0%
```

**Configuration:**
```python
settings.market_data_provider  # "yfinance" or "alpaca"
settings.alpaca_api_key
settings.alpaca_secret_key
```

**Output:** `MarketState`

## Data Models

### ArxivPaper
```python
class ArxivPaper(BaseModel):
    id: str              # ArXiv ID (e.g., "2401.12345")
    title: str           # Paper title
    abstract: str        # Full abstract
    authors: list[str]   # Author names
    categories: list[str]# ArXiv categories
    published: datetime  # Publication date
    url: str             # ArXiv URL
```

### NewsObject
```python
class NewsObject(BaseModel):
    id: str              # Unique identifier
    headline: str        # Article headline
    summary: str         # Article summary (max 500 chars)
    source: str          # Source name
    url: str             # Article URL
    timestamp: datetime  # Publication time
    tickers: list[str]   # Matched tickers
    keywords: list[str]  # Matched keywords
```

### MarketState
```python
class MarketState(BaseModel):
    ticker: str
    price: float
    volume_30d_avg: float
    spread_pct: float
    liquidity_status: LiquidityStatus
    open: float
    high: float
    low: float
    close: float
    volume: int
```

## Error Handling

All fetchers raise `DataFetchError` on failure:

```python
class DataFetchError(VelitesError):
    """Raised when data fetching fails."""
    pass
```

Common error scenarios:
- Missing API keys
- Rate limiting (429 responses)
- Network timeouts
- Invalid responses

## Async Patterns

All fetch methods are async for concurrent execution:

```python
# Concurrent fetching in orchestrator
papers, news, market = await asyncio.gather(
    arxiv_fetcher.fetch_papers(categories),
    news_fetcher.fetch_news(tickers),
    market_fetcher.fetch_batch_market_state(tickers),
)
```

## Dependencies

- `httpx` - Async HTTP client
- `feedparser` - RSS/Atom parsing (ArXiv, RSS feeds)
- `yfinance` - Yahoo Finance (development)
- `alpaca-py` - Alpaca Markets API (production)

## File Structure

```
src/modules/scout/
    __init__.py
    arxiv_fetcher.py
    news_fetcher.py
    market_fetcher.py
    models.py
    exceptions.py
```
