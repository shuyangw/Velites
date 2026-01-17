# Mapper Module Architecture

The Mapper module is Velites' entity resolution layer, translating unstructured text mentions into tradeable US tickers using a semiconductor-focused knowledge graph.

## Purpose

Mapper bridges the gap between:
- **Academic papers** mentioning technologies, companies, or concepts
- **Tradeable securities** on US exchanges

Key capabilities:
- Company name to ticker resolution
- Technology to supplier mapping
- Supply chain traversal
- Non-US ticker normalization (ADR mapping)

## Component Diagram

```
                    +-------------------+
                    |   MAPPER MODULE   |
                    +-------------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
+---------------+   +---------------+   +---------------+
| EntityResolver|   | TickerMapper  |   |KnowledgeGraph |
+---------------+   +---------------+   +---------------+
        |                   |                   |
        v                   v                   v
   Text -> Entities   Entities -> Tickers   Graph Queries
```

## Components

### KnowledgeGraph (`knowledge_graph.py`)

In-memory graph representing semiconductor industry relationships.

**Key Methods:**
- `load()` - Load graph from JSON file
- `get_node(node_id)` - Retrieve node by ID
- `get_suppliers(company_id)` - Upstream suppliers
- `get_customers(company_id)` - Downstream customers
- `get_competitors(company_id)` - Lateral competitors
- `search_by_alias(alias)` - Fuzzy name matching

**Node Types:**
```python
class NodeType(Enum):
    COMPANY = "company"
    TECHNOLOGY = "technology"
    PRODUCT = "product"
    CONCEPT = "concept"
```

**Edge Types:**
```python
class EdgeType(Enum):
    SUPPLIES = "supplies"
    COMPETES_WITH = "competes_with"
    USES = "uses"
    DEVELOPS = "develops"
```

### EntityResolver (`entity_resolver.py`)

Extracts tradeable entities from unstructured text.

**Key Methods:**
- `resolve_text(text)` - Main entry point
- `_extract_entities(text)` - NER-style extraction
- `_match_to_graph(entities)` - Graph lookup
- `_filter_tradeable(nodes)` - US-tradeable filter

**Resolution Pipeline:**
```
Raw Text
    |
    v
Entity Extraction (regex + patterns)
    |
    v
Knowledge Graph Lookup
    |
    v
US-Tradeable Filter
    |
    v
list[TradeableTicker]
```

### TickerMapper (`ticker_mapper.py`)

Maps entities to their tradeable US tickers.

**Key Methods:**
- `map_entity(entity)` - Single entity mapping
- `map_entities(entities)` - Batch mapping
- `normalize_ticker(ticker)` - Non-US to ADR conversion
- `get_risk_flags(ticker)` - Risk assessment

**ADR Mappings:**
```python
ADR_MAPPINGS = {
    "2330.TW": "TSM",    # TSMC
    "005930.KS": "SSNLF", # Samsung
    "6758.T": "SONY",    # Sony
    ...
}
```

## Data Models

### GraphNode
```python
class GraphNode(BaseModel):
    id: str
    name: str
    node_type: NodeType
    aliases: list[str]
    ticker: str | None
    market: str | None
    metadata: dict
```

### TradeableTicker
```python
class TradeableTicker(BaseModel):
    ticker: str          # US ticker symbol
    company_name: str    # Full company name
    confidence: float    # Resolution confidence (0-1)
    source_entity: str   # Original text entity
    risk_flags: list[RiskFlag]
```

### RiskFlag
```python
class RiskFlag(Enum):
    ADR = "ADR"                    # American Depositary Receipt
    SMALL_CAP = "SMALL_CAP"        # Market cap < $2B
    LOW_VOLUME = "LOW_VOLUME"      # Avg volume < 500K
    WIDE_SPREAD = "WIDE_SPREAD"    # Spread > 1%
    RECENT_IPO = "RECENT_IPO"      # IPO < 1 year
    CHINA_EXPOSURE = "CHINA_EXPOSURE"
```

### DependencyMap
```python
class DependencyMap(BaseModel):
    target: str                    # Target ticker
    upstream: list[str]            # Suppliers
    downstream: list[str]          # Customers
    competitors: list[str]         # Competitors
    bottlenecks: list[str]         # Critical dependencies
```

## Knowledge Graph Schema

```json
{
  "nodes": [
    {
      "id": "nvidia",
      "name": "NVIDIA Corporation",
      "type": "company",
      "ticker": "NVDA",
      "market": "NASDAQ",
      "aliases": ["NVIDIA", "NVDA", "Jensen Huang"]
    }
  ],
  "edges": [
    {
      "source": "tsmc",
      "target": "nvidia",
      "type": "supplies",
      "metadata": {"product": "GPU chips"}
    }
  ]
}
```

**Graph Location:** `data/knowledge_graph_v1_2.json`

## Error Handling

```python
class ResolutionError(VelitesError):
    """Raised when entity resolution fails."""
    pass
```

Common scenarios:
- Unknown entity (no graph match)
- Ambiguous entity (multiple matches)
- Non-tradeable entity (no US ticker)

## Resolution Strategies

### Direct Match
```
"NVIDIA" -> knowledge_graph.search("NVIDIA") -> NVDA
```

### Alias Match
```
"Jensen Huang" -> alias lookup -> nvidia node -> NVDA
```

### Technology Cascade
```
"HBM3 memory" -> technology node -> supplier edges -> SK Hynix -> ADR lookup -> HXSCF
```

### Supply Chain Traversal
```
"GPU shortage" -> NVDA -> upstream suppliers -> [TSM, ASML, LRCX]
```

## File Structure

```
src/modules/mapper/
    __init__.py
    knowledge_graph.py
    entity_resolver.py
    ticker_mapper.py
    models.py
    exceptions.py

data/
    knowledge_graph_v1_2.json
```
