# Scribe Module Architecture

The Scribe module is Velites' persistence layer, maintaining a database of all signals for backtesting and performance analysis.

## Purpose

Scribe provides:
- **Signal recording** - Persist every signal with market context
- **Outcome tracking** - Record 7-day price outcomes
- **Backtest queries** - Retrieve historical signals for analysis
- **Performance stats** - Aggregate win rate, returns, best/worst tickers

## Component Diagram

```
                    +-------------------+
                    |  SCRIBE MODULE    |
                    +-------------------+
                            |
            +---------------+---------------+
            |                               |
            v                               v
    +---------------+               +---------------+
    |    Journal    |               | SignalRecord  |
    | (async ops)   |               |  (ORM model)  |
    +---------------+               +---------------+
            |                               |
            v                               v
    +-------+-------+               SQLAlchemy ORM
    |               |
    v               v
  SQLite       PostgreSQL
(aiosqlite)    (asyncpg)
```

## Components

### Journal (`journal.py`)

Async database operations for signal persistence.

**Key Methods:**
- `initialize()` - Create engine, session factory, tables
- `record_signal(signal, market_price)` - Write new signal
- `update_outcome(signal_id, outcome_price, date)` - Update outcome
- `get_signals_for_backtest(start, end, ticker)` - Query signals
- `get_signal_stats(days)` - Aggregate statistics

**Configuration:**
```python
settings.database_url  # "sqlite:///data/velites.db" (dev)
                       # "postgresql://..." (prod)
```

**URL Auto-Conversion:**
```python
# Automatically converts sync URLs to async
"sqlite:///..."     -> "sqlite+aiosqlite:///..."
"postgresql://..."  -> "postgresql+asyncpg://..."
```

### SignalRecord (`db_models.py`)

SQLAlchemy ORM model for signal persistence.

**Schema:**
```python
class SignalRecord(Base):
    __tablename__ = "signal_records"

    id = Column(String, primary_key=True)  # signal_id
    ticker = Column(String, index=True)
    action = Column(String)
    confidence = Column(Float)
    reasoning = Column(Text)
    source_paper_id = Column(String)
    market_price = Column(Float)           # Price at signal time
    outcome_price = Column(Float)          # Price after 7 days
    outcome_date = Column(DateTime)
    created_at = Column(DateTime, index=True)
```

**Indexes:**
- `ticker` - Fast ticker filtering
- `created_at` - Fast date range queries
- `(ticker, created_at)` - Composite for common queries

## Data Models

### JournalEntry
```python
class JournalEntry(BaseModel):
    id: str
    entry_type: JournalEntryType
    timestamp: datetime
    module: str
    message: str
    data: dict | None
    ticker: str | None
    signal_id: str | None
```

### JournalEntryType
```python
class JournalEntryType(Enum):
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_DISPATCHED = "signal_dispatched"
    ENTITY_RESOLVED = "entity_resolved"
    PAPER_PROCESSED = "paper_processed"
    NEWS_PROCESSED = "news_processed"
    ERROR = "error"
    AUDIT = "audit"
```

## Signal Recording Flow

```
AlphaSignal + MarketState
         |
         v
+-------------------+
| journal.record_   |
|      signal()     |
+-------------------+
         |
         v
SignalRecord created
    - signal_id
    - ticker
    - action
    - market_price
    - created_at
         |
         v
Database INSERT
         |
         v
Return signal_id
```

## Outcome Tracking

```
7 days later...
         |
         v
+-------------------+
| journal.update_   |
|    outcome()      |
+-------------------+
         |
         v
Fetch current price
         |
         v
UPDATE signal_records
SET outcome_price = X
    outcome_date = now
WHERE id = signal_id
```

## Statistics Calculation

```python
stats = await journal.get_signal_stats(days=30)

# Returns:
{
    "total_signals": 45,
    "signals_with_outcome": 38,
    "win_rate": 65.8,           # % positive returns
    "avg_return_pct": 2.3,      # Average return
    "best_ticker": "NVDA",      # Highest avg return
    "worst_ticker": "INTC"      # Lowest avg return
}
```

**Win Rate Calculation:**
```python
# For each signal with outcome:
return_pct = (outcome_price - market_price) / market_price * 100
is_win = return_pct > 0

win_rate = sum(wins) / total * 100
```

## Query Patterns

### All Signals
```python
signals = await journal.get_signals_for_backtest()
```

### Filter by Date
```python
signals = await journal.get_signals_for_backtest(
    start_date=datetime(2026, 1, 1),
    end_date=datetime(2026, 1, 31)
)
```

### Filter by Ticker
```python
signals = await journal.get_signals_for_backtest(ticker="NVDA")
```

### Combined Filters
```python
signals = await journal.get_signals_for_backtest(
    start_date=datetime(2026, 1, 1),
    ticker="NVDA"
)
```

## Error Handling

```python
class ScribeError(VelitesError):
    """Base scribe exception."""
    pass

class JournalWriteError(ScribeError):
    """Raised when journal write fails."""
    pass
```

Common scenarios:
- Journal not initialized
- Signal not found (update_outcome)
- Database connection failure
- Constraint violation (duplicate ID)

## Async Session Management

```python
async with self._session_factory() as session:
    # Read
    result = await session.execute(select(SignalRecord))
    records = result.scalars().all()

    # Write
    session.add(record)
    await session.commit()
```

## File Structure

```
src/modules/scribe/
    __init__.py
    journal.py
    db_models.py
    models.py
    exceptions.py

data/
    velites.db          # SQLite database (dev)
```

## Dependencies

- `sqlalchemy` - ORM and query building
- `aiosqlite` - Async SQLite driver
- `asyncpg` - Async PostgreSQL driver (production)
