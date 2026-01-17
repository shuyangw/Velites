# Courier Module Architecture

The Courier module is Velites' signal delivery layer, responsible for formatting, validating, and dispatching trading signals to the Homeguard execution system.

## Purpose

Courier ensures signals are:
- **Validated** - Liquidity checks prevent trading into illiquid markets
- **Formatted** - JSON payloads match Homeguard contract
- **Delivered** - Webhook or file-based dispatch with retry logic

## Component Diagram

```
                    +-------------------+
                    |  COURIER MODULE   |
                    +-------------------+
                            |
            +---------------+---------------+
            |                               |
            v                               v
    +---------------+               +---------------+
    | LiquidityGuard|               |  Dispatcher   |
    +---------------+               +---------------+
            |                               |
            v                       +-------+-------+
    MarketState Check               |               |
            |                       v               v
            v                   Webhook          File
    PASS / NO_GO               (httpx)         (JSON)
```

## Components

### LiquidityGuard (`liquidity_guard.py`)

Pre-trade liquidity validation to prevent slippage.

**Key Methods:**
- `check_liquidity(ticker, market_state)` - Main validation
- `_check_spread(spread_pct)` - Spread threshold
- `_check_volume(volume_30d_avg, price)` - Dollar volume

**Thresholds:**
```python
settings.max_spread_pct   # 2.0% default
settings.min_volume_usd   # $500,000 default
```

**Validation Logic:**
```python
# Check spread
if market_state.spread_pct > max_spread_pct:
    return NO_GO, "Spread too wide"

# Check dollar volume
dollar_volume = market_state.volume_30d_avg * market_state.price
if dollar_volume < min_volume_usd:
    return NO_GO, "Insufficient volume"

return PASS, None
```

### Dispatcher (`dispatcher.py`)

Formats and delivers signals to Homeguard.

**Key Methods:**
- `format_payload(signal)` - Create Homeguard JSON
- `dispatch(signal)` - Send single signal
- `dispatch_batch(signals)` - Send multiple signals
- `_dispatch_webhook(payload)` - HTTP POST with retry
- `_dispatch_file(payload)` - Write to JSON file

**Webhook Retry:**
- 3 attempts with exponential backoff (2s, 4s, 8s)
- 30-second timeout per request
- Falls back to file output on failure

**Configuration:**
```python
settings.homeguard_webhook_url  # Empty = file mode
settings.homeguard_output_dir   # "output/signals"
```

## Data Models

### AlphaSignal
```python
class AlphaSignal(BaseModel):
    signal_id: str           # Unique identifier
    action: SignalAction     # BUY, BUY_LONG, WAIT, IGNORE, NO_GO
    ticker: str              # Target ticker
    venue: str               # "NASDAQ", "NYSE", etc.
    order_type: OrderType    # MARKET or LIMIT
    limit_price: float | None
    confidence: float        # 0.0 to 1.0
    reasoning: str           # Signal explanation
    valid_until: datetime    # Expiration time
    risk_flags: list[RiskFlag]

    # Source tracking
    source_paper_id: str | None
    innovation_score: float | None
    sentiment_score: float | None
```

### SignalAction
```python
class SignalAction(Enum):
    BUY = "BUY"           # Standard buy
    BUY_LONG = "BUY_LONG" # Long position
    WAIT = "WAIT"         # Hold off
    IGNORE = "IGNORE"     # Not relevant
    NO_GO = "NO_GO"       # Failed validation
```

### OrderType
```python
class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
```

## Homeguard Payload Schema

```json
{
  "source": "Velites_v1",
  "signal_id": "velites_abc12345",
  "timestamp": "2026-01-17T12:00:00Z",
  "type": "QUANTAMENTAL_BUY_LONG",
  "ticker": "ASML",
  "venue": "NASDAQ",
  "order_type": "LIMIT",
  "limit_price": 750.50,
  "validity": "24h",
  "confidence": 0.9,
  "reasoning": "ArXiv paper suggests moat expansion...",
  "risk_flags": ["SMALL_CAP"],
  "valid_until": "2026-01-18T10:00:00Z"
}
```

**Signal Type Format:** `QUANTAMENTAL_{action}`

## Dispatch Flow

```
AlphaSignal
     |
     v
+------------------+
|  format_payload  |
+------------------+
     |
     v
Homeguard JSON
     |
     v
webhook_url set?
     |
+----+----+
|         |
YES       NO
|         |
v         v
+--------+ +--------+
|Webhook | | File   |
|  POST  | | Write  |
+--------+ +--------+
     |         |
     v         v
 Success?   Success
     |
+----+----+
|         |
YES       NO
|         |
v         v
Done    Retry (3x)
            |
            v
        Fallback
        to File
```

## Error Handling

```python
class CourierError(VelitesError):
    """Base courier exception."""
    pass

class LiquidityCheckError(CourierError):
    """Raised when liquidity check fails."""
    pass

class DispatchError(CourierError):
    """Raised when dispatch fails."""
    pass
```

## File Output

When webhook is not configured or fails:

```
output/signals/
    velites_abc12345_ASML.json
    velites_def67890_NVDA.json
```

Each file contains the full Homeguard payload.

## File Structure

```
src/modules/courier/
    __init__.py
    liquidity_guard.py
    dispatcher.py
    models.py
    exceptions.py

output/signals/        # File dispatch output
    *.json
```
