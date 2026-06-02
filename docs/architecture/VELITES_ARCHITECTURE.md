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

# Confluence thresholds
settings.confluence_innovation_threshold      # 0.7 (signal if above)
settings.confluence_sentiment_veto_threshold  # -0.5 (veto if below)
settings.confluence_hype_threshold            # 3.0 (hold if above)

# Scheduling
settings.run_mode              # "single" or "scheduled"
settings.run_interval_hours    # 4 (for scheduled mode)
settings.run_at_startup        # True (run immediately on start)
```

## Run Modes

Velites supports two execution modes:

| Mode | Command | Behavior |
|------|---------|----------|
| **Single** | `python -m src.main --mode single` | Run pipeline once and exit |
| **Scheduled** | `python -m src.main --mode scheduled` | APScheduler runs every N hours |

In scheduled mode:
- Pipeline runs immediately if `run_at_startup` is True
- Subsequent runs at `run_interval_hours` intervals
- Graceful shutdown on SIGINT/SIGTERM

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

scripts/
  smoke_test.py     # End-to-end module verification
  view_signals.py   # Query and display journal database
  save_enriched.py  # Capture pipeline state after entity resolution
  replay_signals.py # Regenerate signals with different thresholds
  run_pipeline.py   # Simple pipeline runner
  test_modules.py   # Module import verification
```

## Operational Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `smoke_test.py` | Verify all modules work end-to-end | `python scripts/smoke_test.py --dry-run` |
| `view_signals.py` | Query journal database | `python scripts/view_signals.py --stats` |
| `save_enriched.py` | Save enriched papers for replay | `python scripts/save_enriched.py --output data/enriched.json` |
| `replay_signals.py` | Test different thresholds | `python scripts/replay_signals.py --input data/enriched.json` |

**Replay Workflow:**
```bash
# 1. Save enriched papers (runs Scout + Mapper)
python scripts/save_enriched.py --output data/enriched.json

# 2. Replay with different thresholds (fast iteration)
python scripts/replay_signals.py --input data/enriched.json \
    --innovation-threshold 0.6 --hype-threshold 2.5
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
