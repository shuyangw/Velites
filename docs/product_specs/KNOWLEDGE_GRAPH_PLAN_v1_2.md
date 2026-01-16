# Module 2: The Mapper (Knowledge Graph) - Implementation Plan v1.2

**Last Verified: January 15, 2026**

## Changelog from v1.1
- **Added EDA sector**: Synopsys (SNPS), Cadence (CDNS), Siemens EDA (SIEGY)
- **Added IP cores**: Enhanced ARM coverage, added Rambus (RMBS), CEVA
- **Added emerging materials**: Corning (GLW), Ajinomoto (AJINY), Resonac (PCRFY), Ibiden (IBID)
- **Fixed ticker normalization**: All non-US tickers now have `us_adr` field for Alpaca compatibility
- **Improved SEC parsing strategy**: Focus on Exhibit 10 and Item 1A, not Item 1 fluff

## Key Market Updates
- **HBM Market Share**: Micron (21%) has surpassed Samsung (17-22%) to become #2 behind SK Hynix (57-62%)
- **NVIDIA Rubin**: R100 now in full production, shipping H2 2026; Vera CPU replaces Grace
- **AMD MI350**: Now shipping (MI350X, MI355X); MI400 confirmed for 2026 with 432GB HBM4
- **Intel Falcon Shores**: Cancelled; replaced by Jaguar Shores rack-scale solution (2026-27)

---

## Overview

This module translates "tech speak" into tradeable stock tickers and maps supply chain relationships for identifying lag-play opportunities. The system consists of two sub-modules that work together to provide actionable intelligence when news mentions products, technologies, or companies.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     knowledge_graph.json                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   product_map   │  │  supply_chain   │  │ trading_signals │ │
│  │  (Entity Res.)  │  │   (Tier 1-3)    │  │   (Playbooks)   │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
└───────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌───────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│  resolve_entity() │  │ get_suppliers()   │  │ get_signals()    │
│  "H100" → NVDA    │  │ NVDA → [TSM,...]  │  │ trigger → action │
└───────────────────┘  └───────────────────┘  └──────────────────┘
```

---

## Critical Addition: Ticker Normalization for Alpaca

### The Problem
The original JSON used mixed ticker formats:
- `005930.KS` (Yahoo/Korea) - **Will crash Alpaca**
- `7974.T` (Japan) - **Will crash Alpaca**
- `NVDA` (US) - Works fine

### The Solution
Every non-US ticker now has a `us_adr` field:

```python
def get_tradeable_ticker(entity: dict) -> Optional[str]:
    """Return US-tradeable ticker, or None if track-only."""
    
    # If it's already a US ticker, return it
    ticker = entity.get("ticker")
    if ticker and not any(x in ticker for x in [".KS", ".T", ".TW", ".DE"]):
        return ticker
    
    # Check for US ADR
    us_adr = entity.get("us_adr")
    if us_adr:
        return us_adr
    
    # Check normalization table
    if ticker in TICKER_NORMALIZATION:
        mapping = TICKER_NORMALIZATION[ticker]
        if mapping.get("tradeable_us", True):
            return mapping["us_adr"]
    
    # Not tradeable on US exchanges
    return None
```

### Quick Reference Table

| Native Ticker | US ADR | Liquidity | Tradeable |
|---------------|--------|-----------|-----------|
| 005930.KS (Samsung) | SSNLF | Low (OTC) | Yes, but thin |
| 7974.T (Nintendo) | NTDOY | High | Yes |
| 2454.TW (MediaTek) | MDTKF | Very Low | Track only |
| 2317.TW (Foxconn) | HNHPF | Very Low | Track only |
| 000660.KS (SK Hynix) | SKHIY | Medium | Yes |
| 8035.T (Tokyo Electron) | TOELY | Medium | Yes |
| 2802.T (Ajinomoto) | AJINY | Low | Yes |
| 4004.T (Resonac) | PCRFY | Low | Yes |
| 4062.T (Ibiden) | - | Very Low | Track only |

---

## New Coverage: "Tax Collectors" and "Bottleneck Materials"

### EDA (Electronic Design Automation)
The "toll booth" of chip design - every NVIDIA/AMD/Apple chip requires these tools.

| Ticker | Name | Role | Moat |
|--------|------|------|------|
| SNPS | Synopsys | Chip design, AI-powered EDA | ~35% market share, duopoly |
| CDNS | Cadence | Design, verification, emulation | ~35% market share, duopoly |
| SIEGY | Siemens EDA | DRC/LVS verification (Calibre) | Industry standard for verification |

**Signal correlation**: High with R&D budgets, NOT capex. EDA revenue leads chip design activity by 12-18 months.

### IP Cores
Royalties on every chip shipped - recurring revenue tied to unit volumes.

| Ticker | Name | Role | Moat |
|--------|------|------|------|
| ARM | Arm Holdings | CPU architecture licensing | 99%+ smartphone market |
| RMBS | Rambus | HBM interface IP, security | Critical HBM patents |
| CEVA | CEVA Inc | DSP cores, AI/ML IP | Niche but pure-play |

### Advanced Packaging Materials

| Ticker | Name | Role | Market Position |
|--------|------|------|-----------------|
| GLW | Corning | Glass substrates | Emerging - Intel/Apple 2026+ |
| AJINY | Ajinomoto | ABF substrates | ~99% monopoly |
| PCRFY | Resonac | HBM stacking materials | #1 in die attach film |
| IBID | Ibiden | IC substrates | Major Intel supplier (track only) |

---

## SEC Parsing Strategy: REVISED

### The Original Problem
The v1.1 plan suggested parsing "Item 1 (Business)" of 10-Ks. This is **ineffective** because:
- Item 1 is 50+ pages of marketing fluff
- Companies rarely name specific suppliers (NDAs)
- Common phrasing: "a limited number of third-party suppliers"

### Better Approach: Three-Pronged Strategy

#### 1. Exhibit 10 (Material Contracts) - BEST SOURCE
This is where companies **legally must** attach supply agreements.

```python
def parse_exhibit_10(filing_path: str) -> List[dict]:
    """Extract supplier relationships from Exhibit 10 contracts."""
    
    # Look for these patterns in exhibit titles:
    patterns = [
        r"Supply Agreement",
        r"Manufacturing Agreement", 
        r"Foundry Agreement",
        r"Master Purchase Agreement",
        r"Strategic Alliance",
        r"License Agreement"
    ]
    
    # Extract counterparty names
    relationships = []
    for exhibit in get_exhibits(filing_path, exhibit_type="EX-10"):
        counterparty = extract_counterparty(exhibit)
        if counterparty:
            relationships.append({
                "type": classify_relationship(exhibit.title),
                "counterparty": counterparty,
                "confidence": "high",
                "source": exhibit.filing_id
            })
    
    return relationships
```

#### 2. Item 1A (Risk Factors) - PROPER NOUN EXTRACTION
Companies must disclose material risks, which often names specific dependencies.

```python
def parse_risk_factors(text: str, company_name: str) -> List[str]:
    """Extract supplier names from risk factors section."""
    
    # Key phrases that precede supplier names
    trigger_phrases = [
        r"sole source",
        r"single supplier",
        r"depend(?:s|ent) on",
        r"reliance on",
        r"concentration risk",
        r"manufacturing partner",
        r"foundry partner"
    ]
    
    # Find proper nouns near trigger phrases
    suppliers = []
    for phrase in trigger_phrases:
        matches = re.finditer(
            rf"{phrase}[^.]*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            text, re.IGNORECASE
        )
        for match in matches:
            potential_name = match.group(1)
            if potential_name.lower() != company_name.lower():
                suppliers.append({
                    "name": potential_name,
                    "context": phrase,
                    "confidence": "medium"
                })
    
    return suppliers
```

#### 3. Press Releases (Supplier Awards) - CLEANEST SIGNAL
"Onto Innovation Receives Order from Tier 1 Memory Manufacturer"

```python
# RSS feeds to monitor
PRESS_RELEASE_FEEDS = [
    "https://www.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtXWA==",  # Tech
    "https://www.prnewswire.com/rss/technology-rss.xml",
    # SEC 8-K RSS for material events
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=40&output=atom"
]

def classify_press_release(title: str, body: str) -> Optional[dict]:
    """Identify supplier relationship announcements."""
    
    patterns = {
        "supplier_award": [
            r"receives order",
            r"selected as supplier",
            r"extends partnership",
            r"multi-year agreement"
        ],
        "customer_win": [
            r"selected by",
            r"chosen to provide",
            r"wins contract"
        ]
    }
    
    for rel_type, phrases in patterns.items():
        for phrase in phrases:
            if re.search(phrase, title + body, re.IGNORECASE):
                return {
                    "type": rel_type,
                    "source": "press_release",
                    "confidence": "high"
                }
    
    return None
```

### Implementation Priority

| Source | Signal Quality | Effort | Priority |
|--------|----------------|--------|----------|
| Press releases (supplier awards) | High | Low | **Week 1** |
| Item 1A (risk factors) | Medium-High | Medium | Week 2 |
| Exhibit 10 (contracts) | Highest | High | Week 3-4 |
| Item 1 (business) | Low | Low | Skip |

---

## Sub-Module 2.1: Entity Resolver

### Purpose
When the Scout module detects "H100" or "Blackwell" in news, return the associated ticker(s) and context.

### Data Structure (v1.2)
```json
{
  "H100": {
    "ticker": "NVDA",
    "role": "designer",
    "category": "ai_gpu",
    "architecture": "Hopper",
    "fabricator": "TSM"
  },
  "Galaxy S": {
    "ticker": "SSNLF",
    "native_ticker": "005930.KS",
    "category": "smartphone"
  }
}
```

### Lookup Logic (Updated for Ticker Normalization)
```python
def resolve_entity(term: str) -> dict:
    """Resolve product/company name to ticker info with US-tradeable ticker."""
    
    term_lower = term.lower()
    
    # 1. Check aliases first
    if term_lower in aliases["products"]:
        term = aliases["products"][term_lower]
    if term_lower in aliases["companies"]:
        us_ticker = aliases["companies"][term_lower]
        return {"ticker": us_ticker, "tradeable": True}
    
    # 2. Search product_map
    result = search_product_map(term)
    if result:
        # Normalize to US-tradeable ticker
        native_ticker = result.get("ticker") or result.get("native_ticker")
        us_ticker = result.get("us_adr") or result.get("ticker")
        
        # Check if tradeable on US exchanges
        tradeable = is_us_tradeable(us_ticker)
        
        return {
            **result,
            "ticker": us_ticker,
            "native_ticker": native_ticker,
            "tradeable": tradeable
        }
    
    # 3. Fuzzy match fallback
    return fuzzy_search(term, threshold=0.85)

def is_us_tradeable(ticker: str) -> bool:
    """Check if ticker is tradeable on US exchanges (for Alpaca)."""
    
    # Non-tradeable patterns
    if any(x in str(ticker) for x in [".KS", ".T", ".TW", ".DE"]):
        return False
    
    # Known thin/track-only OTC
    track_only = {"MDTKF", "HNHPF", "IBID"}
    if ticker in track_only:
        return False
    
    return True
```

### Starter Coverage (v1.2)
- **139+ semiconductor products** (NVIDIA, AMD, Intel, Apple, Qualcomm, Broadcom, memory)
- **58 cloud services** (AWS, Azure, GCP, Oracle, IBM)
- **42 AI models** (OpenAI, Anthropic, Google, Meta, Mistral)
- **67 enterprise software products**
- **41 developer/observability tools**
- **23 cybersecurity products**
- **32 consumer electronics**
- **NEW: 6 EDA tools** (Synopsys, Cadence, Siemens EDA)
- **NEW: 5 IP core products** (ARM, Rambus, CEVA)
- **NEW: 4 emerging materials** (Corning, Ajinomoto, Resonac, Ibiden)

---

## Sub-Module 2.2: Supply Chain Mapper

### Purpose
Given a ticker, return suppliers (multi-tier), customers, and competitors for identifying lag plays and correlated moves.

### Data Structure (v1.2 - With EDA/Materials)
```json
{
  "NVDA": {
    "name": "NVIDIA Corporation",
    "tier1_suppliers": {
      "TSM": {"role": "foundry", "revenue_concentration": "sole source"},
      "SKHIY": {"role": "memory", "market_share": "57-62%"},
      "SNPS": {"role": "eda", "products": ["chip design software"]},
      "CDNS": {"role": "eda", "products": ["verification, emulation"]},
      "RMBS": {"role": "ip", "products": ["HBM interface IP"]}
    },
    "tier1_customers": {
      "MSFT": {"products": ["H100", "B200"], "use_case": "Azure AI"}
    },
    "competitors": ["AMD", "INTC", "GOOGL", "AMZN"]
  }
}
```

### Multi-Tier Resolution (Same as v1.1)
```python
def get_supply_chain(ticker: str, depth: int = 2) -> dict:
    result = {"tier1": [], "tier2": [], "tier3": []}
    
    if ticker in supply_chain:
        company = supply_chain[ticker]
        result["tier1"] = list(company.get("tier1_suppliers", {}).keys())
        
        if depth >= 2:
            for supplier in result["tier1"]:
                if supplier in supply_chain:
                    tier2 = supply_chain[supplier].get("tier1_suppliers", {})
                    result["tier2"].extend(tier2.keys())
        
        if depth >= 3:
            for supplier in set(result["tier2"]):
                if supplier in supply_chain:
                    tier3 = supply_chain[supplier].get("tier1_suppliers", {})
                    result["tier3"].extend(tier3.keys())
    
    return {k: list(set(v)) for k, v in result.items()}
```

### Small/Mid-Cap Lag Plays (Updated)

| Ticker | Name | Role | Typical Lag |
|--------|------|------|-------------|
| ENTG | Entegris | Ultra-pure chemicals | 1-2 days |
| PLAB | Photronics | Photomasks | 1-3 days |
| UCTT | Ultra Clean | Gas delivery | 2-3 days |
| ICHR | Ichor Holdings | Subsystems | 1-2 days |
| FORM | FormFactor | Probe cards | 1-2 days |
| ONTO | Onto Innovation | Metrology | 1-2 days |
| ACLS | Axcelis | Ion implant | 1-2 days |
| AMKR | Amkor | Packaging | 1-2 days |
| ASX | ASE Technology | OSAT | 1-2 days |
| **RMBS** | **Rambus** | **HBM IP** | **1-2 days** |
| **PCRFY** | **Resonac** | **HBM materials** | **2-3 days** |

---

## Automatic Update Strategy (Revised)

### Data Sources (By Priority)

#### 1. Press Releases (Free, Real-time) - **START HERE**
**What it provides:** Partnership announcements, supplier additions - cleanest signal

**Sources:**
- SEC 8-K filings (material events)
- BusinessWire/PR Newswire RSS feeds
- Company newsrooms (scraping)

**Implementation:**
```python
import feedparser

def monitor_press_releases():
    """Poll RSS feeds for supplier relationship news."""
    
    feeds = [
        "https://www.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtXWA==",
        "https://www.prnewswire.com/rss/technology-rss.xml"
    ]
    
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if is_supplier_announcement(entry.title, entry.summary):
                yield extract_relationship(entry)
```

**Update frequency:** Real-time / hourly

#### 2. SEC Item 1A / Exhibit 10 (Free, Quarterly)
**What it provides:** Official supplier dependencies from risk factors and contracts

**Key sections:**
- Item 1A (Risk Factors): "sole supplier", "single source" phrases with proper nouns
- Exhibit 10: Actual supply agreements

**Implementation:**
```bash
pip install edgartools --break-system-packages

# Key endpoints
# Submissions: https://data.sec.gov/submissions/CIK{cik}.json
# Full filing text for parsing
```

**Update frequency:** Within 5 days of quarterly filing deadlines

#### 3. Wikipedia/Wikidata (Free, Reference Data)
**What it provides:** Company metadata, product lists, basic relationships

**Update frequency:** Weekly

#### 4. LLM Extraction (Low Cost, Enhancement)
**What it provides:** Structured relationship extraction from Item 1A and press releases

**Cost estimate:** ~$500-1,500/month for 10M tokens using Claude Haiku or GPT-4o mini

**Prompt template:**
```
Extract supplier and customer relationships from this SEC filing risk factors section.

Focus on:
1. Proper nouns that appear after "sole source", "single supplier", "depend on"
2. Named manufacturing partners or foundry relationships
3. Material customer dependencies (10%+ revenue)

Output JSON: {
  "relationships": [
    {"company": "...", "type": "supplier|customer", "category": "...", "confidence": "high|medium|low"}
  ]
}
```

**Update frequency:** Event-driven

### Paid Options (If Budget Allows)

| Source | Cost | Value |
|--------|------|-------|
| **FactSet Revere** | $15-50K/year | 144K relationships, bulk download, historical |
| **Bloomberg SPLC** | $25K/year | 200K relationships, quantified values |
| **ImportGenius** | $1,800/year | Trade flow data from customs records |

**Recommendation:** Start with free sources. Consider FactSet Revere only if you need historical backtesting data for supply chain signals.

---

## Implementation Roadmap (Revised)

### Phase 1: Static Foundation + Press Releases (Week 1)
1. Load `knowledge_graph_v1.2.json` into your system
2. Implement basic lookup functions with ticker normalization:
   - `resolve_entity(term) -> ticker_info`
   - `get_suppliers(ticker) -> [suppliers]`
   - `get_tradeable_ticker(entity) -> us_ticker`
3. Set up press release RSS monitoring (BusinessWire, PR Newswire)
4. Integrate with Scout module for real-time resolution

### Phase 2: SEC Risk Factor Parsing (Weeks 2-3)
1. Set up quarterly 10-K/10-Q parsing pipeline
2. Target initial companies: NVDA, AMD, TSM, ASML, AMAT, LRCX
3. **Focus on Item 1A (Risk Factors)** - extract proper nouns near trigger phrases
4. **Parse Exhibit 10** - extract counterparty names from material contracts
5. Store diffs for human review before merging

### Phase 3: LLM Enhancement (Weeks 4-5)
1. Build Claude Haiku extraction pipeline for risk factor text
2. Implement confidence scoring
3. Add Discord alerts for significant supply chain changes

### Phase 4: Product Codename Tracking (Ongoing)
1. Monitor key events:
   - Apple WWDC, iPhone launch (September)
   - NVIDIA GTC (March), earnings calls
   - AMD FAD (Financial Analyst Day)
   - Intel Innovation
2. Scrape Wikipedia for new product pages
3. Update product_map with new codenames/architectures

---

## File Structure

```
project/
├── data/
│   ├── knowledge_graph_v1.2.json  # Main mapping file
│   ├── ticker_normalization.json  # US ADR mappings
│   ├── sec_extractions/
│   │   ├── nvda_2024_10k_risks.json
│   │   └── nvda_2024_exhibits.json
│   └── updates/
│       └── pending_relationships.json
├── scripts/
│   ├── entity_resolver.py
│   ├── supply_chain.py
│   ├── sec_parser.py            # Risk factors + Exhibit 10 extraction
│   ├── press_release_monitor.py  # RSS feed monitoring
│   ├── update_scheduler.py
│   └── llm_extractor.py
└── tests/
    └── test_mappings.py
```

---

## API Design (Updated)

```python
class KnowledgeGraph:
    def __init__(self, json_path: str):
        self.data = load_json(json_path)
        self.ticker_map = self.data.get("ticker_normalization", {})
    
    def resolve(self, term: str) -> Optional[dict]:
        """Resolve product/company name to ticker info."""
        pass
    
    def get_us_ticker(self, ticker: str) -> Optional[str]:
        """Convert any ticker to US-tradeable equivalent (for Alpaca)."""
        if ticker in self.ticker_map.get("mappings", {}):
            mapping = self.ticker_map["mappings"][ticker]
            if mapping.get("us_adr"):
                return mapping["us_adr"]
        return ticker if self.is_us_ticker(ticker) else None
    
    def is_tradeable(self, ticker: str) -> bool:
        """Check if ticker is tradeable on US exchanges."""
        track_only = self.ticker_map.get("trading_flags", {}).get("track_only", [])
        return ticker not in track_only
    
    def get_suppliers(self, ticker: str, tiers: int = 2) -> dict:
        """Get supplier tickers by tier."""
        pass
    
    def get_customers(self, ticker: str) -> list:
        """Get customer tickers."""
        pass
    
    def get_competitors(self, ticker: str) -> list:
        """Get competitor tickers."""
        pass
    
    def get_signals(self, trigger: str) -> list:
        """Get trading signals for a trigger event."""
        pass
    
    def get_lag_plays(self, ticker: str) -> list:
        """Get small/mid-cap suppliers likely to lag."""
        pass
    
    def get_eda_exposure(self, ticker: str) -> list:
        """Get EDA/IP companies that benefit from this company's chip designs."""
        pass
```

---

## Validation & Testing (Updated)

### Coverage Tests
```python
# Ensure all major products resolve
test_cases = [
    ("H100", "NVDA"),
    ("Blackwell", "NVDA"),
    ("MI300X", "AMD"),
    ("Graviton", "AMZN"),
    ("M4", "AAPL"),
    ("TPU", "GOOGL"),
    # New v1.2 tests
    ("Fusion Compiler", "SNPS"),
    ("Palladium", "CDNS"),
    ("ABF", "AJINY"),
]

for product, expected_ticker in test_cases:
    result = kg.resolve(product)
    us_ticker = kg.get_us_ticker(result["ticker"])
    assert us_ticker == expected_ticker
```

### Ticker Normalization Tests
```python
def test_ticker_normalization():
    """Ensure all non-US tickers map to tradeable equivalents."""
    
    # Samsung should normalize to SSNLF
    assert kg.get_us_ticker("005930.KS") == "SSNLF"
    
    # Nintendo should normalize to NTDOY  
    assert kg.get_us_ticker("7974.T") == "NTDOY"
    
    # MediaTek is track-only
    assert kg.is_tradeable("MDTKF") == False
    
    # US tickers pass through
    assert kg.get_us_ticker("NVDA") == "NVDA"
```

### Supply Chain Integrity
```python
def test_eda_in_supply_chain():
    """Ensure EDA companies are in chip designer supply chains."""
    
    nvda_suppliers = kg.get_suppliers("NVDA")
    assert "SNPS" in nvda_suppliers["tier1"]
    assert "CDNS" in nvda_suppliers["tier1"]
    
    # EDA companies should have all chip designers as customers
    snps_customers = kg.get_customers("SNPS")
    assert all(c in snps_customers for c in ["NVDA", "AMD", "AAPL", "QCOM"])
```

---

## Trading Signal Examples (New for v1.2)

### EDA Leading Indicator Play
```python
# When a major chip company announces new architecture,
# EDA companies see increased licensing/revenue
def eda_signal_handler(news_event: dict):
    if "new architecture" in news_event["title"].lower():
        company = kg.resolve(news_event["company"])
        
        if company["category"] in ["ai_gpu", "soc", "server_cpu"]:
            # EDA companies benefit from new design starts
            return {
                "signal": "eda_design_start",
                "long": ["SNPS", "CDNS"],
                "confidence": "medium",
                "lag": "0-1 days"  # EDA moves quickly on design news
            }
```

### HBM Materials Play
```python
# HBM shortage news benefits both memory makers AND materials suppliers
def hbm_shortage_handler(news_event: dict):
    if "hbm shortage" in news_event["title"].lower():
        return {
            "signal": "hbm_constraint",
            "long": [
                "MU",      # #2 memory maker benefits from pricing
                "PCRFY",   # Resonac - HBM stacking materials
                "RMBS"     # Rambus - HBM interface IP royalties
            ],
            "lag": "1-3 days"
        }
```

---

## Cost Summary (Updated)

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Press release monitoring | $0 | Free RSS feeds |
| SEC EDGAR parsing | $0 | Free API, 10 req/sec |
| Wikidata queries | $0 | Free SPARQL endpoint |
| LLM extraction | $500-1,500 | Claude Haiku @ 10M tokens |
| Compute (cron jobs) | $50-100 | AWS Lambda or EC2 spot |
| **Total** | **$550-1,600/month** | |

Optional paid enhancements:
- FactSet Revere: +$15-50K/year (historical data, bulk relationships)
- ImportGenius: +$1,800/year (trade flow signals)

---

## Next Steps

1. **Immediate**: Load `knowledge_graph_v1.2.json` and wire up to Scout module
2. **This week**: 
   - Test entity resolution on recent news articles
   - Set up press release RSS monitoring
   - Implement ticker normalization in trading logic
3. **Next sprint**: Build SEC Item 1A parser (skip Item 1 - it's fluff)
4. **Backlog**: LLM extraction pipeline, Exhibit 10 parsing
