# Velites Phases 0-2 + Phase-3 Cheap Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Velites CI-green on a clean checkout, reconcile the docs, promote the smoke test into a CI-gated integration test, then run the three cheapest Phase-3 kill-checks (resolution density, universe decision, price-only benchmark) before any expensive historical-data build.

**Architecture:** Five sequential phases, each its own git branch + PR. Phase 0's `ruff format` lands first so parallel branches rebase onto it. Phases 0-2 are mechanical engineering; the Phase-3 cheap checks are research scripts whose output can STOP the project before the multiple-XL data build (3.P) is ever started.

**Tech Stack:** Python 3.11, pytest + pytest-asyncio, ruff, mypy, structlog, pydantic v2, GitHub Actions. Conda env `fintech` for all local runs.

**Source spec:** `docs/superpowers/specs/2026-06-03-velites-resumption-execution-design.md`

**Conventions for every task below:**
- Run Python via the `fintech` env: `conda run -n fintech python ...` / `conda run -n fintech pytest ...` (or activate it once per shell).
- ASCII-only in all code/docs (repo rule). Use `->`, `[+]`, `[-]`, `[!]`.
- Commit messages end with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Do NOT push without explicit user approval.

---

## Phase 0 - Repo rehabilitation

Branch: `phase-0-repo-rehab`. **Task 0.1 (ruff format) must be the first commit.**

- [ ] **Step 0.0: Create the branch**

```bash
git checkout main && git pull
git checkout -b phase-0-repo-rehab
```

### Task 0.1: Ruff format + lint-config migration (FIRST commit)

**Files:**
- Modify: `pyproject.toml:107-124` (ruff config block)
- Modify: all of `src/` and `tests/` (formatting only)

- [ ] **Step 1: Migrate the ruff config to the `[tool.ruff.lint]` namespace**

Replace the current block (`pyproject.toml` lines 107-124):

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.isort]
known-first-party = ["modules", "config", "logging_config", "exceptions"]
```

with:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["modules", "config", "logging_config", "exceptions"]
```

- [ ] **Step 2: Run the formatter**

Run: `conda run -n fintech ruff format src/ tests/`
Expected: ruff reports "N files reformatted, M files left unchanged" with no errors.

- [ ] **Step 3: Run the linter and confirm config is no longer deprecated**

Run: `conda run -n fintech ruff check src/ tests/`
Expected: NO deprecation warning about top-level `select`/`ignore` (proves Step 1 worked). A list of lint findings may print.

- [ ] **Step 4: Apply safe autofixes, then triage the remainder**

Run: `conda run -n fintech ruff check --fix src/ tests/`
Then re-run `conda run -n fintech ruff check src/ tests/`.
Triage rule for anything still reported:
- Genuine defect (unused import, bare except, mutable default) -> fix it.
- Rule drift / stylistic disagreement on already-working code -> add the rule code to `ignore` in `[tool.ruff.lint]` with a one-line `#` comment justifying it. Do NOT silence `F` (pyflakes) findings; those are real.

- [ ] **Step 5: Re-run format + lint to confirm clean**

Run: `conda run -n fintech ruff format --check src/ tests/ && conda run -n fintech ruff check src/ tests/`
Expected: format check passes; lint exits 0.

- [ ] **Step 6: Run the unit suite to confirm formatting broke nothing**

Run: `conda run -n fintech pytest tests/unit -q`
Expected: same pass/skip counts as before (baseline: 188 passed, 6 skipped).

- [ ] **Step 7: Commit (this is the rebase base for Phase 1)**

```bash
git add pyproject.toml src/ tests/
git commit -m "Apply ruff format and migrate lint config to [tool.ruff.lint]"
```

### Task 0.2: Finish the `datetime.utcnow()` sweep (D6)

`datetime.utcnow()` returns a naive datetime; the codebase standard is tz-aware `datetime.now(timezone.utc)`. Four files remain.

**Files:**
- Modify: `src/modules/courier/dispatcher.py:64`
- Modify: `src/modules/scout/news_fetcher.py:302`
- Modify: `tests/unit/modules/courier/test_liquidity_guard.py:75`
- Modify: `tests/unit/modules/scout/test_news_fetcher.py` (lines 77, 87, 97, 107, 148, 169, 187)

- [ ] **Step 1: Fix `dispatcher.py:64`**

Change:
```python
            "timestamp": datetime.utcnow().isoformat() + "Z",
```
to:
```python
            "timestamp": datetime.now(timezone.utc).isoformat(),
```
(`datetime.now(timezone.utc).isoformat()` already includes the `+00:00` offset, so drop the manual `"Z"`.) Confirm `timezone` is imported at the top of the file; if the import line is `from datetime import datetime`, change it to `from datetime import datetime, timezone`.

- [ ] **Step 2: Fix `news_fetcher.py:302`**

Change `timestamp = datetime.utcnow()` to `timestamp = datetime.now(timezone.utc)`. `timezone` is already imported (`news_fetcher.py:10`).

- [ ] **Step 3: Fix the two test files**

In `tests/unit/modules/courier/test_liquidity_guard.py` and `tests/unit/modules/scout/test_news_fetcher.py`, replace every `datetime.utcnow()` with `datetime.now(timezone.utc)`. Ensure each file imports `timezone` (add to the existing `from datetime import ...` line if missing).

Run to find any stragglers: `conda run -n fintech python -c "import subprocess,sys; sys.exit(0)"` then
`git grep -n "datetime.utcnow()" -- src tests`
Expected: no matches.

- [ ] **Step 4: Reformat touched files + run affected tests**

Run: `conda run -n fintech ruff format src/modules/courier/dispatcher.py src/modules/scout/news_fetcher.py tests/unit/modules/courier/test_liquidity_guard.py tests/unit/modules/scout/test_news_fetcher.py`
Run: `conda run -n fintech pytest tests/unit/modules/courier/test_liquidity_guard.py tests/unit/modules/scout/test_news_fetcher.py -q`
Expected: PASS (same counts as baseline).

- [ ] **Step 5: Commit**

```bash
git add src/modules/courier/dispatcher.py src/modules/scout/news_fetcher.py tests/unit/modules/courier/test_liquidity_guard.py tests/unit/modules/scout/test_news_fetcher.py
git commit -m "Replace naive datetime.utcnow() with tz-aware datetime.now(timezone.utc)"
```

### Task 0.3: Remove the misleading Tiingo constant (D9)

**Files:**
- Modify: `src/modules/scout/news_fetcher.py:22`

- [ ] **Step 1: Confirm the constant is unused**

Run: `git grep -n "TIINGO_NEWS_URL" -- src tests`
Expected: only the definition at `news_fetcher.py:22` (the live fetch at line ~173 builds the `/tiingo/news` URL inline). If any consumer exists, STOP and reconcile instead of deleting.

- [ ] **Step 2: Delete the dead constant**

Remove line 22:
```python
# Tiingo API configuration
TIINGO_NEWS_URL = "https://api.tiingo.com/iex"
```
(Delete the comment line above it too if it only headed this constant.)

- [ ] **Step 3: Confirm imports/module still load**

Run: `conda run -n fintech python -c "import sys; sys.path.insert(0,'src'); import modules.scout.news_fetcher; print('[+] import ok')"`
Expected: `[+] import ok`.

- [ ] **Step 4: Commit**

```bash
git add src/modules/scout/news_fetcher.py
git commit -m "Remove dead misleading TIINGO_NEWS_URL constant pointing at /iex"
```

### Task 0.4: Declare apscheduler (D8)

`run_scheduled` imports `apscheduler` but it is undeclared, so a fresh venv ImportErrors.

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml:25-56` (dependencies array)

- [ ] **Step 1: Add to `requirements.txt`**

After the `# Async HTTP` / `httpx` block (around line 7), add:
```
# Scheduling
apscheduler>=3.10
```

- [ ] **Step 2: Add to `pyproject.toml` dependencies**

Inside the `dependencies = [ ... ]` array, after the `# Async` group, add:
```toml
    # Scheduling
    "apscheduler>=3.10",
```

- [ ] **Step 3: Verify it imports in the env**

Run: `conda run -n fintech python -c "import apscheduler; print('[+]', apscheduler.__version__)"`
Expected: `[+] 3.x` (if missing, `conda run -n fintech pip install "apscheduler>=3.10"`).

- [ ] **Step 4: Verify `run_scheduled` imports cleanly**

Run: `conda run -n fintech python -c "import sys; sys.path.insert(0,'src'); from main import run_scheduled; print('[+] run_scheduled import ok')"`
Expected: `[+] run_scheduled import ok`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pyproject.toml
git commit -m "Declare apscheduler dependency (fixes run_scheduled in clean env)"
```

### Task 0.5: Repoint CI off the dead `src/velites` paths (D2/D3)

**Files:**
- Modify: `.github/workflows/ci.yml:53` (mypy)
- Modify: `.github/workflows/ci.yml:74` (pytest cov)

- [ ] **Step 1: Repoint mypy**

Change line 53 from:
```yaml
        run: mypy src/velites --ignore-missing-imports
```
to:
```yaml
        run: mypy src --ignore-missing-imports
```

- [ ] **Step 2: Run mypy locally and triage**

Run: `conda run -n fintech mypy src --ignore-missing-imports`
- If it exits 0: done.
- If `[tool.mypy] strict = true` surfaces a large backlog of real errors: this is a genuine D2 consequence. Triage rule: fix cheap/obvious annotations; for a large pre-existing backlog that is out of scope for repo-rehab, scope the CI job to the modules that pass and record the deferral in the PR description (do NOT silently delete the type-check job). Capture the decision in a one-line comment in `ci.yml` above the mypy step.

- [ ] **Step 3: Repoint the coverage path**

Change line 74 from:
```yaml
          pytest tests/ -v --cov=src/velites --cov-report=xml
```
to:
```yaml
          pytest tests/ --cov-report=xml
```
(`pyproject.toml` `addopts` already supplies `-v --cov=modules --cov-report=term-missing`, so this yields a single `--cov=modules` with an added xml report - no double-`--cov`.)

- [ ] **Step 4: Reproduce the CI test job locally**

Run: `conda run -n fintech pytest tests/ --cov-report=xml`
Expected: tests pass; `coverage.xml` written; coverage measured against `modules` (visible in the term-missing table).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Repoint CI mypy and coverage off dead src/velites paths to src/modules"
```

### Task 0.6: Phase 0 acceptance gate

- [ ] **Step 1: Full local CI reproduction**

Run each, expecting success:
```bash
conda run -n fintech ruff check src/
conda run -n fintech ruff format --check src/
conda run -n fintech mypy src --ignore-missing-imports
conda run -n fintech pytest tests/ --cov-report=xml
```

- [ ] **Step 2: Fresh-venv scheduler import check**

```bash
python -m venv /tmp/velites-clean
/tmp/velites-clean/bin/python -m pip install -q -r requirements.txt
/tmp/velites-clean/bin/python -c "import sys; sys.path.insert(0,'src'); from main import run_scheduled; print('[+] clean-venv run_scheduled import ok')"
```
(Windows: `py -m venv $env:TEMP\velites-clean` then `& $env:TEMP\velites-clean\Scripts\python.exe ...`.)
Expected: `[+] clean-venv run_scheduled import ok`.

- [ ] **Step 3: Open the PR (do not push until user approves)**

Phase 0 done when all four CI jobs are green on a clean checkout and the clean-venv import succeeds.

---

## Phase 1 - Orientation and doc reconciliation

Branch: `phase-1-docs`, **rebased onto Task 0.1's format commit** (not raw main):

```bash
git checkout phase-0-repo-rehab && git checkout -b phase-1-docs
```

### Task 1.1: Fix Mapper architecture doc (D5)

**Files:**
- Modify: `docs/architecture/MAPPER_ARCHITECTURE.md`

- [ ] **Step 1: Find the stale names**

Run: `git grep -n -E "knowledge_graph\.py|entity_resolver\.py|ticker_mapper\.py|EntityResolver" -- docs/architecture/MAPPER_ARCHITECTURE.md`

- [ ] **Step 2: Replace with the real component names**

Map every occurrence: `knowledge_graph.py` -> `graph_engine.py`; `entity_resolver.py` -> `graph_engine.py` (resolution lives in `GraphEngine.resolve_text`); `ticker_mapper.py` -> `ticker_normalizer.py`; `EntityResolver` -> `GraphEngine`. Add a sentence noting `SupplyChainNavigator` (`supply_chain.py`) as the supply-chain traversal component. Verify the real files: `git ls-files src/modules/mapper`.

- [ ] **Step 3: Confirm no stale names remain**

Run: `git grep -n -E "knowledge_graph\.py|entity_resolver\.py|ticker_mapper\.py|EntityResolver" -- docs/architecture/MAPPER_ARCHITECTURE.md`
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/MAPPER_ARCHITECTURE.md
git commit -m "Fix stale Mapper component names in architecture doc"
```

### Task 1.2: Populate README

**Files:**
- Modify: `README.md` (currently one line)

- [ ] **Step 1: Write the README**

Replace the file with content covering: one-paragraph thesis (innovation-lag edge: research leads, news lags; trade the gap when innovation high + news quiet; veto on >3 sigma hype); the 5-module DAG as an ASCII diagram (Scout -> Mapper -> Analyst -> Courier -> Scribe with one-line roles); run modes (`python -m src.main --mode single|scheduled`); the ops scripts (`smoke_test.py --dry-run`, `replay_signals.py`, `save_enriched.py`, `view_signals.py`); the separation of concerns (Velites generates, Homeguard executes); and a link to `docs/planning/20260602_velites_resumption_plan.md`. ASCII-only. Keep it under ~80 lines.

- [ ] **Step 2: Sanity-check the run commands named in the README actually exist**

Run: `conda run -n fintech python -m src.main --help` and `conda run -n fintech python scripts/smoke_test.py --help`
Expected: both print usage without error.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Populate README with thesis, DAG, run modes, and ops scripts"
```

### Task 1.3: Verify CLAUDE.md reflects run modes + scripts

**Files:**
- Read: `CLAUDE.md` (verify; modify only if gaps found)

- [ ] **Step 1: Check coverage**

Run: `git grep -n -E "--mode|scheduled|smoke_test|replay_signals|save_enriched|view_signals" -- CLAUDE.md`
- If run modes and the four ops scripts are described: no change; note "verified" in the PR.
- If anything is missing: add a short section mirroring the README's run-modes/scripts content, ASCII-only.

- [ ] **Step 2: Commit only if changed**

```bash
git add CLAUDE.md
git commit -m "Document run modes and ops scripts in CLAUDE.md"
```

### Task 1.4: Commit the resumption plan to its repo home

**Files:**
- Create: `docs/planning/20260602_velites_resumption_plan.md`

- [ ] **Step 1: Copy the source plan into the repo**

Copy `C:\Users\qwqw1\Downloads\20260602_velites_resumption_plan_v2.md` to `docs/planning/20260602_velites_resumption_plan.md` verbatim. Create the `docs/planning/` dir if absent.

- [ ] **Step 2: Commit**

```bash
git add docs/planning/20260602_velites_resumption_plan.md
git commit -m "Add v2 resumption plan to docs/planning"
```

### Task 1.5: Phase 1 acceptance gate

- [ ] **Step 1: Cold-reader check**

Re-read `README.md` + `CLAUDE.md` top-to-bottom. Confirm a reader with zero prior context can state: the thesis, the data flow (DAG), and the exact run commands. Fix any gap, recommit. Open the PR (no push without approval).

---

## Phase 2 - Promote smoke test into a CI-gated integration test

Branch: `phase-2-integration` off `main` (after Phase 0 merges) or off `phase-0-repo-rehab`:

```bash
git checkout phase-0-repo-rehab && git checkout -b phase-2-integration
```

### Task 2.1: Write the mocked full-DAG integration test

The orchestrator `VelitesOrchestrator.run_pipeline()` (`src/main.py:80`) calls, in order: `arxiv_fetcher.fetch_papers` + `filter_generic_papers`, `graph_engine.resolve_text`, `supply_chain.get_dependencies`, `llm_agent.grade_innovation`, `news_fetcher.fetch_news`, `sentiment_engine.analyze_sentiment`, `confluence_engine.generate_signal`, `ticker_normalizer.normalize`, `market_fetcher.fetch_market_state`, `liquidity_guard.validate_signal`, `dispatcher.dispatch`, `journal.record_signal`. We mock the four external seams (arxiv, news, market, LLM, sentiment) and run the real graph/confluence/liquidity/journal logic against an in-memory DB.

**Files:**
- Modify: `tests/integration/test_pipeline.py` (replace the two skipped stubs)

- [ ] **Step 1: Write the failing integration test**

Replace the entire contents of `tests/integration/test_pipeline.py` with:

```python
"""Integration tests for the full Velites pipeline (mocked external I/O, zero live calls)."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from modules.analyst.models import InnovationScore, SentimentScore
from modules.scout.models import LiquidityStatus, MarketState, PaperObject
from modules.scribe import Journal


def _make_orchestrator(tmp_path, monkeypatch):
    """Build an orchestrator with every external I/O seam mocked. No network, no LLM, no disk DB."""
    from main import VelitesOrchestrator

    orch = VelitesOrchestrator()

    # In-memory journal (no disk write)
    orch.journal = Journal(database_url="sqlite+aiosqlite:///:memory:")

    # File-mode dispatcher into a temp dir (no webhook)
    orch.dispatcher.webhook_url = ""
    orch.dispatcher.output_dir = tmp_path

    # --- Scout seams ---
    async def fake_fetch_papers(*args, **kwargs):
        return [
            PaperObject(
                id="arxiv_test_0001",
                title="A novel GPU architecture for transformer inference",
                abstract="We present a novel NVIDIA Blackwell-class GPU design that doubles "
                "transformer inference throughput via custom attention kernels.",
                authors=["A. Researcher"],
                url="https://arxiv.org/abs/test.0001",
                published_date=datetime.now(timezone.utc),
                source="arxiv",
                categories=["cs.AR"],
            )
        ]

    async def fake_fetch_news(tickers, *args, **kwargs):
        return []  # quiet news -> no hype veto

    async def fake_fetch_market_state(ticker, *args, **kwargs):
        return MarketState(
            ticker=ticker,
            price=500.0,
            volume_30d_avg=5_000_000,
            spread_pct=0.1,
            liquidity_status=LiquidityStatus.HIGH,
            open=495.0,
            high=505.0,
            low=490.0,
            close=500.0,
            volume=4_000_000,
        )

    monkeypatch.setattr(orch.arxiv_fetcher, "fetch_papers", fake_fetch_papers)
    monkeypatch.setattr(orch.news_fetcher, "fetch_news", fake_fetch_news)
    monkeypatch.setattr(orch.market_fetcher, "fetch_market_state", fake_fetch_market_state)

    # --- Analyst seams (no API key, no model download) ---
    async def fake_grade_innovation(text, ticker, ticker_context, paper_id, *args, **kwargs):
        return InnovationScore(
            score=0.85, reasoning="mocked", ticker=ticker, paper_id=paper_id
        )

    async def fake_analyze_sentiment(news, ticker, *args, **kwargs):
        return SentimentScore(score=0.1, hype_volume=0.5, is_veto=False, ticker=ticker)

    monkeypatch.setattr(orch.llm_agent, "grade_innovation", fake_grade_innovation)
    monkeypatch.setattr(orch.sentiment_engine, "analyze_sentiment", fake_analyze_sentiment)

    return orch


@pytest.mark.asyncio
async def test_full_pipeline_run_mocked(tmp_path, monkeypatch):
    """The full Scout->Scribe DAG runs end-to-end with mocked I/O and produces a recorded signal."""
    orch = _make_orchestrator(tmp_path, monkeypatch)
    await orch.initialize()

    signals = await orch.run_pipeline()

    # A high-innovation, quiet-news paper on a graph-resolvable ticker should yield a dispatched signal.
    assert isinstance(signals, list)
    assert len(signals) >= 1
    sig = signals[0]
    assert sig.ticker  # resolved + normalized
    assert sig.confidence > 0

    # The signal reached the journal.
    stats = await orch.journal.get_signal_stats()
    assert stats["total_signals"] >= 1

    # The dispatcher wrote a signal file (file mode), proving Courier ran with no webhook.
    files = list(tmp_path.glob("*.json"))
    assert files, "expected a dispatched signal file"


@pytest.mark.asyncio
async def test_pipeline_no_entities_returns_empty(tmp_path, monkeypatch):
    """A paper that resolves to no entities yields zero signals without error."""
    orch = _make_orchestrator(tmp_path, monkeypatch)

    async def fake_fetch_papers_unresolvable(*args, **kwargs):
        return [
            PaperObject(
                id="arxiv_test_0002",
                title="On the asymptotics of abstract measure spaces",
                abstract="A purely theoretical result with no company, product, or ticker references.",
                authors=["B. Theorist"],
                url="https://arxiv.org/abs/test.0002",
                published_date=datetime.now(timezone.utc),
                source="arxiv",
                categories=["math.PR"],
            )
        ]

    monkeypatch.setattr(orch.arxiv_fetcher, "fetch_papers", fake_fetch_papers_unresolvable)
    await orch.initialize()

    signals = await orch.run_pipeline()
    assert signals == []
```

- [ ] **Step 2: Run it and verify it fails first for the right reason (red), then passes (green)**

Run: `conda run -n fintech pytest tests/integration/test_pipeline.py -v`
Expected on first run: if any mocked seam name is wrong (e.g. a model field mismatch), it fails with a clear AttributeError/ValidationError - fix the mock to match the real model, not the test's intent. Once correct: both tests PASS. Confirm the run made zero network calls (no `httpx`/ArXiv log lines; only the mocked path executes).

- [ ] **Step 3: Confirm the old skip markers are gone**

Run: `git grep -n "Requires full implementation" -- tests/integration/test_pipeline.py`
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_pipeline.py
git commit -m "Replace skipped pipeline stubs with mocked CI-gated integration test"
```

### Task 2.2: Audit the remaining skips

**Files:**
- Read: all test files (audit only)

- [ ] **Step 1: Enumerate skips**

Run: `conda run -n fintech pytest tests/ -rs -q`
Expected: the `-rs` summary lists every skipped test with its reason.

- [ ] **Step 2: Classify each skip**

For each remaining skip, confirm it matches the spec's OQ-5 benign set: FinBERT model-download skip, and the inverted "dependency-absent" guards that skip because the dep IS present. Any skip that hides real coverage loss -> file a follow-up note in the PR description (do not fix here unless trivial). There should be no integration-stub skips left after Task 2.1.

- [ ] **Step 3: Commit (only if any test file changed during the audit)**

```bash
git add tests/
git commit -m "Audit and annotate intentional test skips"
```

### Task 2.3: Phase 2 acceptance gate

- [ ] **Step 1: Confirm integration coverage runs clean with zero live calls**

Run: `conda run -n fintech pytest tests/integration -v`
Expected: all integration tests pass; no network/LLM activity. Open the PR (no push without approval).

---

## Phase 3 cheap kill-checks (3.0, 3.U, 3.1)

Branch: `phase-3-cheap-checks` off `main` (after Phase 2) or off `phase-2-integration`.
These run BEFORE the multiple-XL historical-data build (3.P). Any one can STOP the project. Research artifacts go under `scripts/research/` and `docs/research/` (not shipped as product code), except the watchlist filter in Task 3.U-B which is a real pipeline change.

### Task 3.0: Resolution-density check (recent sample, zero API spend)

Measures what fraction of recent ArXiv abstracts resolve to any ticker, with an on/off-watchlist breakdown, to decide whether the signal is dense enough to validate.

**Files:**
- Create: `scripts/research/resolution_density.py`
- Create: `tests/research/test_resolution_density.py`
- Create: `docs/research/2026-06-03-resolution-density.md` (results, written after the run)

- [ ] **Step 1: Write the failing test for the pure measurement function**

Create `tests/research/test_resolution_density.py`:

```python
"""Tests for the resolution-density measurement helper."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))

from resolution_density import DensityResult, measure_density


class FakeEntity:
    def __init__(self, ticker):
        self.ticker = ticker
        self.confidence = 0.9


class FakeResolver:
    """Resolves text to a ticker iff a known keyword appears."""

    def __init__(self, mapping):
        self._mapping = mapping  # keyword -> ticker

    def resolve_text(self, text):
        hits = []
        low = text.lower()
        for kw, tkr in self._mapping.items():
            if kw in low:
                hits.append(FakeEntity(tkr))
        return hits


def test_measure_density_fraction_and_watchlist_split():
    resolver = FakeResolver({"nvidia": "NVDA", "acme": "ACME"})
    texts = [
        "NVIDIA announces a new GPU",       # resolves, on-watchlist
        "ACME cloud platform launch",        # resolves, off-watchlist
        "A purely theoretical math result",  # no resolution
        "nvidia and acme partner up",        # resolves (primary = first/highest)
    ]
    watchlist = {"NVDA"}

    result = measure_density(texts, resolver, watchlist)

    assert isinstance(result, DensityResult)
    assert result.total == 4
    assert result.resolved == 3
    assert result.resolution_fraction == pytest.approx(0.75)
    assert result.on_watchlist >= 1
    assert result.off_watchlist >= 1
    assert result.on_watchlist + result.off_watchlist == result.resolved


import pytest  # noqa: E402  (imported late so the helper import error surfaces first)
```

- [ ] **Step 2: Run it; expect failure (module missing)**

Run: `conda run -n fintech pytest tests/research/test_resolution_density.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolution_density'`.

- [ ] **Step 3: Implement the helper + script**

Create `scripts/research/resolution_density.py`:

```python
"""Resolution-density check (Phase 3.0).

Measures what fraction of a recent ArXiv sample resolves to any ticker, with an
on/off-watchlist breakdown. Zero API spend - uses the existing GraphEngine resolver
over recent papers (the recent fetcher, not the unbuilt historical harvester).

Usage:
    python scripts/research/resolution_density.py --lookback-hours 168 --max-results 100
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@dataclass
class DensityResult:
    total: int
    resolved: int
    on_watchlist: int
    off_watchlist: int

    @property
    def resolution_fraction(self) -> float:
        return self.resolved / self.total if self.total else 0.0


def measure_density(texts, resolver, watchlist) -> DensityResult:
    """Pure function: run resolver over texts, tally resolution + watchlist split."""
    resolved = 0
    on_wl = 0
    off_wl = 0
    wl = {t.upper() for t in watchlist}
    for text in texts:
        entities = resolver.resolve_text(text)
        if not entities:
            continue
        resolved += 1
        primary = max(entities, key=lambda e: e.confidence)
        if primary.ticker.upper() in wl:
            on_wl += 1
        else:
            off_wl += 1
    return DensityResult(total=len(texts), resolved=resolved, on_watchlist=on_wl, off_watchlist=off_wl)


def _load_watchlist() -> set[str]:
    from config import settings

    path = Path(settings.watchlist_path)
    if not path.exists():
        logger.info("watchlist_absent", path=str(path))
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        tickers = data.get("tickers", list(data.keys()))
    else:
        tickers = data
    return {str(t).upper() for t in tickers}


async def _run(lookback_hours: int, max_results: int) -> DensityResult:
    from modules.scout import ArxivFetcher
    from modules.mapper import GraphEngine

    fetcher = ArxivFetcher()
    fetcher.max_results = max_results
    papers = await fetcher.fetch_papers(lookback_hours=lookback_hours)
    papers = fetcher.filter_generic_papers(papers)

    engine = GraphEngine()
    engine.load_graph()

    texts = [f"{p.title} {p.abstract}" for p in papers]
    watchlist = _load_watchlist()
    result = measure_density(texts, engine, watchlist)

    logger.info(
        "resolution_density",
        total=result.total,
        resolved=result.resolved,
        fraction=round(result.resolution_fraction, 3),
        on_watchlist=result.on_watchlist,
        off_watchlist=result.off_watchlist,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3.0 resolution-density check")
    parser.add_argument("--lookback-hours", type=int, default=168)
    parser.add_argument("--max-results", type=int, default=100)
    args = parser.parse_args()

    result = asyncio.run(_run(args.lookback_hours, args.max_results))

    print("=" * 60)
    print("RESOLUTION DENSITY (Phase 3.0)")
    print("=" * 60)
    print(f"Papers sampled:       {result.total}")
    print(f"Resolved to a ticker: {result.resolved} ({result.resolution_fraction:.1%})")
    print(f"  on-watchlist:       {result.on_watchlist}")
    print(f"  off-watchlist:      {result.off_watchlist}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test; expect pass**

Run: `conda run -n fintech pytest tests/research/test_resolution_density.py -v`
Expected: PASS.

- [ ] **Step 5: Run the real check and record results**

Run: `conda run -n fintech python scripts/research/resolution_density.py --lookback-hours 168 --max-results 100`
Capture the printed numbers into `docs/research/2026-06-03-resolution-density.md` with: the sample size/window, resolution fraction, on/off-watchlist split, 5-10 hand-verified examples (real vs coincidental substring hits), and a one-line verdict: PROCEED / STOP / REDIRECT-TO-KG. Reference the spec's kill condition (too sparse or too noisy -> STOP or Phase 5).

- [ ] **Step 6: Commit**

```bash
git add scripts/research/resolution_density.py tests/research/test_resolution_density.py docs/research/2026-06-03-resolution-density.md
git commit -m "Add Phase 3.0 resolution-density check with results"
```

### Task 3.U: Universe decision

Settle the watchlist fork the spec verified (pipeline emits off-watchlist today). The 3.0 on/off split informs the choice. Pick ONE sub-task.

**Files (decision record, always):**
- Create: `docs/research/2026-06-03-universe-decision.md`

- [ ] **Step 1: Write the decision record**

In `docs/research/2026-06-03-universe-decision.md`, state the chosen option and rationale, citing the 3.0 numbers and the verified finding (`main.py:151` emits on `primary.ticker`, no watchlist gate; `config.py:29` `watchlist_path` unused). Record the consequence for capacity (3.6) and survivorship (3.8): option A -> capacity non-issue; option B -> capacity is a live GATE criterion.

#### Option A (filter to the 11-name watchlist) - implement Task 3.U-A
**Files:**
- Modify: `src/modules/mapper/graph_engine.py` (or `src/main.py` resolution step) to drop resolutions whose ticker is not in the loaded watchlist
- Create: `data/watchlist.json` if absent (the 11 names: NVDA, TSM, ASML, AMD, ... per the plan)
- Create: `tests/unit/modules/mapper/test_watchlist_filter.py`

- [ ] **A-Step 1: Write the failing test** (filter keeps on-watchlist, drops off-watchlist resolutions). Mirror the `FakeResolver` style from Task 3.0; assert the post-filter ticker set is a subset of the watchlist.
- [ ] **A-Step 2:** Run -> fail.
- [ ] **A-Step 3:** Implement the filter where `primary` is chosen (`main.py:162` region) or as a `GraphEngine` method, gated by the loaded `watchlist_path`. Keep it a pure, separately-tested function.
- [ ] **A-Step 4:** Run -> pass; run the Phase-2 integration test to confirm the NVDA fixture still produces a signal.
- [ ] **A-Step 5:** Commit `feat: filter resolved entities to the configured watchlist`.

#### Option B (accept broad emission) - implement Task 3.U-B
- [ ] **B-Step 1:** No code change to emission. Add a test asserting the documented behavior (off-watchlist tickers can be emitted) so it is intentional and locked: `tests/unit/modules/mapper/test_broad_emission.py` resolves a text to an off-watchlist ticker and asserts it survives. Run -> pass.
- [ ] **B-Step 2:** Record in the decision doc that 3.6 capacity becomes a live GATE criterion and 3.P must pull a PIT universe spanning the broad resolved set.
- [ ] **B-Step 3:** Commit `docs: accept broad off-watchlist emission as the Phase-3 universe`.

- [ ] **Final step (both options): Commit the decision record**

```bash
git add docs/research/2026-06-03-universe-decision.md
git commit -m "Record Phase 3.U universe decision"
```

### Task 3.1: Price-only benchmark bar

Establish the bar the signal must clear on universe `U`, using only adjusted historical prices (no corpus, no harvester). Names the price source and requires a PIT-correct universe.

**Files:**
- Create: `scripts/research/benchmark_bar.py`
- Create: `tests/research/test_benchmark_bar.py`
- Create: `docs/research/2026-06-03-benchmark-bar.md` (results)

- [ ] **Step 1: Write failing tests for the pure metric functions**

Create `tests/research/test_benchmark_bar.py` testing two pure functions against hand-computed values:

```python
"""Tests for benchmark-bar metric helpers (pure functions, deterministic)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))

from benchmark_bar import annualized_sharpe, buy_and_hold_returns


def test_buy_and_hold_returns_equal_weight():
    # Two assets, each +10% over the window -> portfolio +10%.
    prices = {
        "AAA": [100.0, 110.0],
        "BBB": [50.0, 55.0],
    }
    total = buy_and_hold_returns(prices)
    assert total == pytest.approx(0.10)


def test_annualized_sharpe_known_series():
    # Constant positive daily return -> very high, finite Sharpe; zero std guard returns 0.
    daily = np.array([0.001] * 252)
    sharpe = annualized_sharpe(daily)
    assert sharpe > 0
    assert np.isfinite(sharpe)
    assert annualized_sharpe(np.array([0.0, 0.0, 0.0])) == 0.0
```

- [ ] **Step 2: Run -> fail (module missing).**

Run: `conda run -n fintech pytest tests/research/test_benchmark_bar.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the benchmark script**

Create `scripts/research/benchmark_bar.py` with: the two pure functions below, plus a price loader that names the source explicitly (Alpaca SIP if `settings.alpaca_api_key` is set, else yfinance), pulls split/dividend-ADJUSTED daily closes for universe `U` over a fixed window, and computes (1) equal-weight buy-and-hold total return + annualized Sharpe and (2) a simple monthly cross-sectional momentum long-top-quintile return + Sharpe. Universe `U` is read from `data/watchlist.json` (option A) or from a `--universe` CSV (option B). Print a table; this is the bar 3.5 must beat on a residual basis.

```python
"""Phase 3.1 price-only benchmark bar.

Establishes sector-beta (buy-and-hold) and plain cross-sectional momentum baselines
on universe U, using ONLY adjusted historical prices. No corpus, no harvester.

Price source: Alpaca SIP (adjusted) if credentials present, else yfinance (auto_adjust=True).
Requires a point-in-time-correct universe (include delisted/acquired names) - see spec 3.8.

Usage:
    python scripts/research/benchmark_bar.py --start 2022-01-01 --end 2024-12-31 --universe data/watchlist.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

TRADING_DAYS = 252


def buy_and_hold_returns(prices: dict[str, list[float]]) -> float:
    """Equal-weight buy-and-hold total return across assets (first->last adjusted close)."""
    per_asset = []
    for _, series in prices.items():
        if len(series) >= 2 and series[0] > 0:
            per_asset.append(series[-1] / series[0] - 1.0)
    return float(np.mean(per_asset)) if per_asset else 0.0


def annualized_sharpe(daily_returns: np.ndarray, rf: float = 0.0) -> float:
    """Annualized Sharpe of a daily-return series; 0.0 if std is zero/degenerate."""
    r = np.asarray(daily_returns, dtype=float)
    if r.size < 2:
        return 0.0
    excess = r - rf / TRADING_DAYS
    sd = excess.std(ddof=1)
    if sd == 0 or not np.isfinite(sd):
        return 0.0
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / sd)


def _load_universe(spec: str) -> list[str]:
    path = Path(spec)
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return [str(t).upper() for t in data.get("tickers", list(data.keys()))]
        return [str(t).upper() for t in data]
    # CSV: one ticker per line
    return [line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_adjusted_closes(tickers: list[str], start: str, end: str) -> dict[str, list[float]]:
    """Adjusted daily closes per ticker. Names the source; logs which one is used."""
    from config import settings

    if settings.alpaca_api_key and settings.alpaca_secret_key:
        logger.info("price_source", source="alpaca_sip")
        # NOTE: implement via alpaca-py StockHistoricalDataClient with adjustment="all".
        # Kept explicit so the source is named per spec; falls through to yfinance if unavailable.
        try:
            return _alpaca_closes(tickers, start, end)
        except Exception as e:  # noqa: BLE001
            logger.error("alpaca_price_fetch_failed", error=str(e))
    logger.info("price_source", source="yfinance")
    return _yfinance_closes(tickers, start, end)


def _yfinance_closes(tickers: list[str], start: str, end: str) -> dict[str, list[float]]:
    import yfinance as yf

    out: dict[str, list[float]] = {}
    for t in tickers:
        df = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)
        if df is not None and not df.empty:
            out[t] = [float(x) for x in df["Close"].tolist()]
        else:
            logger.info("no_price_data", ticker=t)  # delisted/missing -> survivorship flag
    return out


def _alpaca_closes(tickers: list[str], start: str, end: str) -> dict[str, list[float]]:
    from datetime import datetime

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from config import settings

    client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    req = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        adjustment="all",
    )
    bars = client.get_stock_bars(req).df
    out: dict[str, list[float]] = {}
    for t in tickers:
        if t in bars.index.get_level_values(0):
            out[t] = [float(x) for x in bars.loc[t]["close"].tolist()]
        else:
            logger.info("no_price_data", ticker=t)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3.1 price-only benchmark bar")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--universe", required=True, help="watchlist.json or a CSV of tickers")
    args = parser.parse_args()

    tickers = _load_universe(args.universe)
    prices = _load_adjusted_closes(tickers, args.start, args.end)
    missing = [t for t in tickers if t not in prices]

    bh = buy_and_hold_returns(prices)
    # Equal-weight daily portfolio returns for Sharpe.
    series = [np.diff(np.asarray(v)) / np.asarray(v[:-1]) for v in prices.values() if len(v) >= 2]
    if series:
        min_len = min(len(s) for s in series)
        port_daily = np.mean(np.vstack([s[:min_len] for s in series]), axis=0)
    else:
        port_daily = np.array([])
    bh_sharpe = annualized_sharpe(port_daily)

    print("=" * 60)
    print("PRICE-ONLY BENCHMARK BAR (Phase 3.1)")
    print("=" * 60)
    print(f"Universe size:            {len(tickers)} ({len(prices)} with data, {len(missing)} missing)")
    if missing:
        print(f"  MISSING (survivorship?): {missing}")
    print(f"Buy-and-hold total return: {bh:.1%}")
    print(f"Buy-and-hold ann. Sharpe:  {bh_sharpe:.2f}")
    print("=" * 60)
    print("[!] Missing tickers may indicate survivorship bias - require a PIT universe (spec 3.8).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests; expect pass**

Run: `conda run -n fintech pytest tests/research/test_benchmark_bar.py -v`
Expected: PASS (pure functions; no network).

- [ ] **Step 5: Run the real benchmark and record results**

Run: `conda run -n fintech python scripts/research/benchmark_bar.py --start 2022-01-01 --end 2024-12-31 --universe data/watchlist.json`
Record into `docs/research/2026-06-03-benchmark-bar.md`: the price source used, universe size + any missing (survivorship flag), buy-and-hold return + Sharpe, momentum baseline, and the explicit statement that this is the residual bar for 3.5. Note whether plain momentum is already deflated-Sharpe-positive (reframes the edge question).

- [ ] **Step 6: Commit**

```bash
git add scripts/research/benchmark_bar.py tests/research/test_benchmark_bar.py docs/research/2026-06-03-benchmark-bar.md
git commit -m "Add Phase 3.1 price-only benchmark bar with results"
```

### Task 3.cheap: Cheap-checks gate

- [ ] **Step 1: Synthesize the three results**

Read the three research docs. If 3.0 density is adequate, 3.U is settled, and 3.1 establishes a beatable-but-real bar, PROCEED to the separate 3.P+ plan. If 3.0 is too sparse/noisy, STOP or REDIRECT-TO-KG (Phase 5). Record the call in `docs/research/2026-06-03-cheap-checks-gate.md`. Open the PR (no push without approval).

---

## Self-review notes (author)

- **Spec coverage:** Phase 0 covers D2/D3/D4/D6/D8/D9 (tasks 0.1-0.5); Phase 1 covers D5 + README + CLAUDE.md + plan-home (1.1-1.4); Phase 2 covers smoke->integration promotion + skip audit (2.1-2.2); Phase 3 covers 3.0 density, 3.U universe fork (both options), 3.1 benchmark with named price source + survivorship flag. Phase-0 acceptance (CI green + clean-venv import) and the gate tasks map to the spec's acceptance bars. 3.P/3.2-3.8 and Phases 4-6 are intentionally OUT of this plan (separate plan after the cheap-checks gate).
- **Placeholder scan:** mypy-strict triage (0.5 Step 2) and ruff-check triage (0.1 Step 4) are real iterative tasks with exact commands + decision rules, not placeholders. The Alpaca price path is fully written with a yfinance fallback.
- **Type consistency:** `DensityResult`/`measure_density`, `annualized_sharpe`/`buy_and_hold_returns`, and the orchestrator seam names (`fetch_papers`, `fetch_news`, `fetch_market_state`, `grade_innovation`, `analyze_sentiment`) match the real signatures verified in `src/main.py` and the module models.
