# Velites Architecture Overview

Velites is a quantamental research agent that identifies alpha opportunities by combining academic research signals with market data and sentiment analysis.

## System Overview

```
                              +------------------+
                              |     VELITES      |
                              |   Orchestrator   |
                              +--------+---------+
                                       |
         +------------+----------------+----------------+------------+
         |            |                |                |            |
         v            v                v                v            v
    +--------+   +--------+       +--------+       +--------+   +--------+
    | SCOUT  |   | MAPPER |       | ANALYST|       | COURIER|   | SCRIBE |
    | Module |   | Module |       | Module |       | Module |   | Module |
    +--------+   +--------+       +--------+       +--------+   +--------+
         |            |                |                |            |
    Data Fetch   Entity Map      Analysis        Dispatch      Persist
```

## Module Summary

| Module | Role | Key Components |
|--------|------|----------------|
| **Scout** | Data acquisition | ArXiv papers, Tiingo news, market data |
| **Mapper** | Entity resolution | Knowledge graph, ticker mapping, supply chains |
| **Analyst** | Signal generation | LLM grading, FinBERT sentiment |
| **Courier** | Signal delivery | Payload formatting, webhook dispatch, liquidity checks |
| **Scribe** | Persistence | SQLite/PostgreSQL journal, backtest queries |

## Data Flow

```
1. SCOUT fetches ArXiv papers, news, and market data
                    |
                    v
2. MAPPER resolves entities to tradeable US tickers
                    |
                    v
3. ANALYST grades innovation relevance and sentiment
                    |
                    v
4. COURIER validates liquidity and dispatches signals
                    |
                    v
5. SCRIBE records signals for backtesting
```

## Core Abstractions

### Models (Pydantic)

Each module defines strongly-typed data models:

- `ArxivPaper`, `NewsObject`, `MarketState` (Scout)
- `TradeableTicker`, `RiskFlag`, `DependencyMap` (Mapper)
- `InnovationScore`, `SentimentResult` (Analyst)
- `AlphaSignal`, `SignalAction`, `OrderType` (Courier)
- `JournalEntry`, `SignalRecord` (Scribe)

### Exceptions

Custom exception hierarchy for error handling:

```
VelitesError (base)
    +-- DataFetchError (Scout)
    +-- ResolutionError (Mapper)
    +-- LLMError, SentimentError (Analyst)
    +-- DispatchError, LiquidityCheckError (Courier)
    +-- JournalWriteError (Scribe)
```

### Async Architecture

All I/O operations use async/await:

- `httpx.AsyncClient` for HTTP requests
- `aiosqlite` for database operations
- Concurrent paper/news/market fetching

## Configuration

Settings loaded from environment via Pydantic:

```python
from config import settings

# API keys
settings.tiingo_api_key
settings.anthropic_api_key
settings.alpaca_api_key

# Module settings
settings.llm_provider          # "openai" or "anthropic"
settings.market_data_provider  # "yfinance" or "alpaca"
settings.database_url          # SQLite or PostgreSQL
```

## Directory Structure

```
src/
  modules/
    scout/          # Data acquisition
    mapper/         # Entity resolution
    analyst/        # Signal analysis
    courier/        # Signal dispatch
    scribe/         # Persistence
  config.py         # Pydantic settings
  logging_config.py # Structured logging
  main.py           # Orchestrator

tests/
  unit/modules/     # Unit tests per module
  integration/      # Cross-module tests
```

## Key Design Decisions

1. **Modular Architecture**: Each module is self-contained with its own models, exceptions, and tests

2. **Async-First**: All I/O is async for concurrent data fetching and database operations

3. **Strongly Typed**: Pydantic models enforce data contracts between modules

4. **Provider Abstraction**: Market data (yfinance/Alpaca) and LLM (OpenAI/Anthropic) are swappable

5. **Graceful Degradation**: Missing API keys or failed fetches don't crash the system

## See Also

- [Scout Architecture](./SCOUT_ARCHITECTURE.md)
- [Mapper Architecture](./MAPPER_ARCHITECTURE.md)
- [Analyst Architecture](./ANALYST_ARCHITECTURE.md)
- [Courier Architecture](./COURIER_ARCHITECTURE.md)
- [Scribe Architecture](./SCRIBE_ARCHITECTURE.md)
