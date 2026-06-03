# Velites Resumption - Execution Design Spec

**Date:** 2026-06-03
**Status:** PROPOSED (awaiting user review)
**Source plan:** `20260602_velites_resumption_plan_v2.md` (to be committed to `docs/planning/20260602_velites_resumption_plan.md` in Phase 1)
**Scope decision:** Plan all 6 phases at task-level detail. Phases 4-6 are tagged conditional on a Phase-3 GO.

**Spec revision (this version) incorporates 6 review catches:**
1. The watchlist fork is universe-defining (not a doc item) - promoted to an explicit early decision that fixes the universe for all universe-dependent Phase-3 steps.
2. Historical ArXiv acquisition is unbuilt engineering on the critical path - added as a gating prerequisite; Phase 3 re-tagged multiple-XL.
3. The dual-model contamination probe has a capability confound - the within-model placebo is promoted to primary; dual-model becomes corroboration.
4. Price/return source named; point-in-time-correct (survivorship-safe) universe snapshot required.
5. GATE "sane capacity" reconciled with 3.6 (capacity is conditional on the universe decision).
6. Hype-veto baseline must be causal/trailing-only when reconstructed historically.

---

## Context

Velites is a 5-module quantamental signal service (Scout -> Mapper -> Analyst -> Courier -> Scribe) spun out of Homeguard. Thesis: an **innovation-lag edge** - research leads, news lags; trade the gap when innovation is high and news is quiet, veto on hype (>3 sigma news volume). Velites *generates* signals; Homeguard *executes*.

Six commits pushed 2026-06-02 (`855c9a1` -> `7b4205c`) resolved most of v1's Phase 0-2 tooling. This spec converts the v2 resumption plan into an executable sequence. The center of gravity is **Phase 3** - a STOP/GO validation gate whose outcome can archive the project. The engineering before it (Phases 0-2) exists to make a Phase-3 result *believable*; the work after it (Phases 4-6) only happens on a GO.

This spec is the execution design. It does not itself implement anything; the next step is the writing-plans skill, which turns each phase below into a step-by-step implementation plan.

### Verified current state (inspected at `7b4205c`, 2026-06-03)

| Item | Finding |
|---|---|
| D2/D3 CI dead paths | CONFIRMED. `ci.yml:53` runs `mypy src/velites`; `ci.yml:74` runs `pytest --cov=src/velites`. Packages live under `src/` directly; `pyproject.toml` sets `--cov=modules`. CI also stacks `--cov=src/velites` on top of pyproject's `--cov=modules` (double conflict). |
| D4 ruff drift | CONFIRMED. `pyproject.toml` uses deprecated top-level `[tool.ruff] select/ignore` and `[tool.ruff.isort]` instead of `[tool.ruff.lint.*]`. Newer ruff warns. |
| D8 apscheduler | CONFIRMED absent from both `requirements.txt` and `pyproject.toml` dependencies. |
| Phase 1 README | CONFIRMED one line (`# Velites`). |
| CI Python | Pinned 3.11. |
| **Watchlist scope** | **CONFIRMED: no watchlist filter in the resolution->signal path.** `GraphEngine.resolve_text` (`graph_engine.py:140`) matches the full company-alias set + the entire `product_map` (cloud, AI models, cybersecurity, consumer electronics - beyond the 11 semis). `main.py:151` takes `primary = max(entities, key=confidence)` and emits on `primary.ticker` with no watchlist gate. Configured `watchlist_path` (`config.py:29`) is defined but unreferenced. The pipeline can emit off-watchlist signals today; the plan's "11-name universe" is not what the pipeline produces. **This defines the universe for all universe-dependent Phase-3 steps - see decision 3.U.** |
| **Historical ArXiv** | **CONFIRMED: the ArXiv fetcher is recent-polling-only.** `arxiv_fetcher.py:88-94` builds `...&max_results={max_results}&sortBy=submittedDate&sortOrder=descending` with no `submittedDate:[start TO end]` range and no `start=` pagination; L92 caps at `max_results` (default 100); L121-122 filters client-side `if updated < cutoff_date: continue`. It physically cannot reach papers older than the most recent ~100 per category. **A historical ArXiv harvester does not exist and is on the critical path for the backtest - see 3.P.** |

---

## Execution approach

**Chosen: sequential, gate-respecting.** Mirror the plan's critical path - Phases 0 and 1 in parallel (cheap, independent) -> Phase 2 -> **Phase 3 gate** -> 4/5/6 on GO. Within Phase 3, run the cheapest kill-checks first (resolution density, universe decision, price-only benchmark) before the contamination probe, and before the expensive historical-data build, so the most likely STOP reasons surface for the least effort.

Rejected alternatives:
- **Defect-batched** (land all D2-D9 first ignoring phase boundaries): faster to CI-green but tangles Phase-0 CI fixes with Phase-1 docs and loses the phase narrative.
- **Risk-first** (jump to Phase-3 probes before Phase 2): front-loads the verdict but runs the probes on an un-CI-verified DAG, weakening trust in the results. We borrow only its idea of ordering cheap probes early - inside Phase 3, not ahead of CI hygiene.

### Branch / commit / PR structure

- One branch + PR per phase; atomic commits (one logical unit each) per repo convention.
- **Phase 0's `ruff format` commit lands first; all other branches rebase onto it** to avoid reformat churn across parallel work. Phase 1 (parallel) rebases onto the format commit, not raw `main`.
- No pushing without explicit user approval (house rule).
- Phase 3 research artifacts live under `docs/` (or a research dir), NOT shipped to `main` as product code - with two exceptions that are ship-quality infra and land in `main` behind the module structure: the **historical data harvesters (3.P)** and the **grade cache (3.3)**.
- Environment: `fintech` conda env (verified to carry the deps).

---

## Phase 0 - Repo rehabilitation (S)

Branch `phase-0-repo-rehab`. **Commit order matters** (format first).

1. **D4 (first commit): `ruff format src/ tests/`** as an isolated reformat, plus migrate config to `[tool.ruff.lint] select/ignore` and `[tool.ruff.lint.isort]`. Triage `ruff check` findings against the repo-pinned ruff (some are rule drift, not real defects). Land this before opening other branches; rebase Phase 1 onto it.
2. **D2/D3:** repoint CI - `mypy src/velites` -> `mypy src`; remove the CLI `--cov=src/velites` so the job uses pyproject's `--cov=modules` (or set `--cov=modules` explicitly). Verify no double-`--cov`.
3. **D8:** declare `apscheduler` in `requirements.txt` and `pyproject.toml` dependencies.
4. **D6:** finish the `datetime.utcnow()` sweep (tests + any stragglers). Decide CI Python: **pin 3.11 now** (matches current pin and mypy target); revisit 3.12 at Phase 6 productionization.
5. **D9:** fix or remove the misleading `TIINGO_NEWS_URL = ".../iex"` constant (`news_fetcher.py:22`); the live fetch at line 173 already uses `/tiingo/news`.

**Acceptance:** all 4 CI jobs (lint, type-check, test, build) green on a clean checkout; `run_scheduled` imports cleanly in a fresh venv.

---

## Phase 1 - Orientation and doc reconciliation (S)

Branch `phase-1-docs` (parallel to Phase 0; rebased onto the format commit).

1. **D5:** fix `MAPPER_ARCHITECTURE.md` component names -> `graph_engine.py` / `supply_chain.py` / `ticker_normalizer.py`; note `EntityResolver` -> `GraphEngine` and the added `SupplyChainNavigator`.
2. Populate `README.md`: thesis, DAG diagram, run modes, link to the resumption plan.
3. Verify (do not assume) the rewritten `CLAUDE.md` reflects the new run modes + ops scripts post-`7b4205c`.
4. Commit the resumption plan to `docs/planning/20260602_velites_resumption_plan.md`.
5. Record the watchlist-scope finding here, but note the *decision* is made at **3.U** (it is universe-defining, not a doc cleanup) and may require a pipeline code change.

**Acceptance:** a cold reader can state the thesis, data flow, and run commands from README + CLAUDE.md.

---

## Phase 2 - Promote smoke test into CI-gated integration coverage (S-M)

Branch `phase-2-integration`.

1. Confirm `smoke_test.py --dry-run` runs the full DAG with mocked LLM/sentiment and **zero live calls**.
2. Extract its core into `tests/integration/test_pipeline.py`, replacing the 2 skipped stubs, so Scout->Scribe is CI-verified.
3. Audit the skipped tests (the +2 are inverted dependency-absent guards per OQ-5; confirm intentional, not silent coverage loss).

**Acceptance:** `pytest tests/integration` exercises Scout->Scribe with zero live calls; no unexplained skips.

---

## Phase 3 - Signal validation study (GATE: STOP / PIVOT / GO) (multiple-XL)

Branch `phase-3-validation`. Research artifacts under `docs/` except the historical harvesters (3.P) and the grade cache (3.3), which are ship-quality and land in `main`.

**Effort note:** the plan's L-XL tag was light. Once the three point-in-time (PIT) data sources are counted - historical ArXiv (hard, unbuilt), historical Tiingo news (medium), split/dividend-adjusted PIT prices (easier but survivorship-sensitive) - this is **multiple-XL**.

**Ordering principle: cheapest kill-checks first.** Checks that need no historical harvester precede the build; the build (3.P) gates every historical-era step (3.2 onward).

### 3.0 Resolution-density check (FIRST; zero API spend; recent papers; can STOP)
Run `GraphEngine.resolve_text` over a **recent** ArXiv sample (recent so it needs no historical harvester yet). Measure:
- **Resolution fraction** - what share of abstracts resolve to any ticker. ArXiv abstracts describe methods ("a diffusion transformer for..."), not products/tickers, so resolution may fire too rarely (signal too sparse to validate) or too loosely (generic terms -> noise).
- **Semantic soundness** - spot-check that resolutions are real, not coincidental substring hits.
- Measured against the **full KG entity set** (per the watchlist-scope finding), with a breakdown of on- vs off-watchlist resolutions.

**Kill condition:** if density is too sparse or too noisy to support validation, STOP or redirect to Phase 5 KG work before any grading or data build.

### 3.U Universe decision (settle the watchlist fork; defines the universe for 3.1/3.5/3.6/3.8)
The verified finding is that the pipeline emits off-watchlist today. This is **universe-defining**, so it must be settled before any universe-dependent step. Informed by 3.0's on/off-watchlist breakdown, choose explicitly:
- **(A) Add the watchlist filter** - restrict emission to the 11-name semi watchlist (mega/large-cap; capacity a non-issue). Pipeline code change (wire `watchlist_path`).
- **(B) Accept broad emission** - the universe is the full resolved set (includes cloud/cyber/consumer names, some small/mid-cap). Then **capacity is a live Phase-3 concern (3.6), not a deferred Phase-5 one**, and the survivorship/PIT-universe requirement (3.P) widens.

"Validate on 11 semis" and "validate on a broad, partly-unknown resolved set" are two different studies. The chosen universe `U` is referenced by 3.1, 3.5, 3.6, 3.8 below.

### 3.1 Price-only benchmark bar (needs historical prices only; no harvester, no corpus)
Establish the bar the signal must clear on universe `U`, using only price data:
- Buy-and-hold `U` (sector beta).
- Plain cross-sectional momentum on `U`.

**Price source (named): split/dividend-adjusted historical prices via Alpaca SIP (preferred) or yfinance (fallback);** require a **PIT-correct universe snapshot** so delisted/acquired names are present (otherwise survivorship bias re-enters through the data layer - see 3.8). In this period plain semi momentum is likely already deflated-Sharpe-positive, reframing the question to "does innovation-lag add **residual** alpha on top of that." (Signal-vs-baseline *attribution* is deferred to 3.5, since it needs the signal.)

### 3.P Historical data acquisition (UNBUILT ENGINEERING; ship-quality -> main; GATES 3.2 and 3.3)
This is real, previously-unbudgeted engineering on the critical path:
- **Historical ArXiv harvester (the hard one):** a paginated (`start=`), date-ranged (`submittedDate:[start TO end]`), rate-limited (ArXiv asks ~3s between calls; results capped per query) harvester. The current fetcher (`arxiv_fetcher.py:88-94`) is recent-100-only and cannot do this. Build as a new fetcher mode that can land in `main`.
- **Historical Tiingo news (tractable):** `fetch_from_tiingo` already accepts `startDate`; this is a pagination/querying job. Filter on availability time (`publishedDate`/`crawlDate`), not a backfilled timestamp (PIT correctness - OQ-1).
- **Prices:** per 3.1 - named source, PIT-correct, survivorship-safe universe.

**Note:** 3.0 (recent sample) and 3.1 (prices only) do not need this. Everything from 3.2 onward does.

### 3.2 Lookahead contamination probe (placebo PRIMARY; dual-model CORROBORATION)
A 2026-trained model grading a 2023 paper already knows how the tech/ticker played out, inflating historical innovation scores. Two tests, ordered by robustness:

- **PRIMARY - within-model placebo (no capability confound):** with a single (current) model, test whether the innovation score "predicts" forward returns for papers published *after* the price move, where forward causality is impossible. Predictive power there can only be leakage, so it measures contamination *within one model* and avoids the capability confound.
- **CORROBORATION - dual-model cutoff differential:** grade the same papers with (i) a current frontier model and (ii) a model whose training cutoff predates each paper; compare forward-return predictiveness. **Caveat (stated):** the old-cutoff model is also *less capable*, so a weaker correlation confounds lack-of-future-knowledge (wanted) with worse grading (capability). Use only to corroborate the placebo, not as the sole measure. **Named dependency:** an accessible old-cutoff model; if none exists, rely on the placebo alone.

**Forward-validation feasibility (power calculation) - part of this step:** the signal is low-frequency (a few resolved papers/week on `U`). Given expected signals/week and a hypothesized per-signal effect, compute how long a forward period must run to reach significance. **An ~18-month answer is itself a decision-relevant finding (potential STOP); forward validation is not a free fallback.**

Run 3.2 on a **small historical slice** (cheaper than the full corpus) so the contamination verdict precedes the full corpus build.

**Branch on the probe:**
- Small leakage -> historical backtest is valid for the full signal.
- Large leakage -> the innovation score is gated by a forward paper-trading period (feasibility per the power calc); historical replay is used only for the less-contaminated parts (threshold/cost/portfolio sensitivity).

### 3.3 Grade cache (ship-quality -> main) + full historical corpus build
- **Grade cache:** persist `InnovationScore` + `SentimentScore` keyed by `(paper_id, model, prompt_version)`, so threshold replay reads cached grades and costs nothing per sweep. Lands in `main` behind the module structure (on a GO it caches grades live for reproducibility / no re-grading). Precondition that makes the sweep affordable.
- **Full corpus:** ArXiv submission timestamp = causal (via 3.P harvester); PIT Tiingo news; forward returns at 1d/5d/20d on `U`; persisted via `save_enriched.py` format.
- **Causal hype baseline (PIT):** the >3 sigma news-volume veto must be computed against a **trailing-only** rolling distribution when reconstructed historically. A centered or full-sample window leaks future news into the baseline. Reconstruct the hype baseline causally.

### 3.4 Threshold sweep wrapped in a proper protocol
Use `replay_signals.py` for the sweep, but wrap it:
- **Walk-forward + CPCV** with purge/embargo over the news/price overlap.
- **Embargo pinned numerically: >= max label horizon + news-availability lag.** With overlapping 20-day forward labels, **embargo >= 20d + lag**, stated explicitly so it cannot be under-embargoed (adjacent samples share outcome windows and leak otherwise).
- **Deflated / probabilistic Sharpe to pay for the search. Trial count N = the FULL researcher DoF**, not just the threshold grid: thresholds x horizons (1/5/20d) x universe definition x confluence-logic variants x model choice. Scoping N to the threshold sweep under-counts trials, under-deflates, and overstates significance (the Lopez de Prado failure mode).
- Re-confirm the hype baseline is causal/trailing within each fold (per 3.3).

### 3.5 Residual attribution (needs the signal)
Attribute returns on `U` to market + sector + momentum (+ size, given dispersion in `U`) and report **residual alpha, not raw return**, against the 3.1 bar and a shuffled-timestamp / shuffled-paper null. Direct echo of the Homeguard finding that plain momentum beat the regime overlay: plain sector exposure may beat the innovation signal.

### 3.6 Cost model + capacity (capacity criticality depends on 3.U)
Empirical spreads (not heuristic tiers). **Capacity criticality is conditional on the universe decision:**
- If 3.U = (A) 11 mega/large-caps: capacity is a non-issue (hundreds of millions to billions $/day).
- If 3.U = (B) broad emission: small/mid-cap names (e.g. PLAB ~$1.5B, UCTT ~$2.5B) make **capacity a live gate criterion now**, not a deferred Phase-5 question.

### 3.7 Threshold-stability map (0.7 / -0.5 / 3 sigma)
Plateau vs cherry-pick.

### 3.8 Survivorship check (on the PIT universe)
Semi (and broader, if 3.U=B) delistings / M&A. Relies on the **PIT-correct universe snapshot** from 3.P/3.1 so survivorship is not silently reintroduced by a present-day price pull.

### GATE decision
**GO** requires: passing 3.0 (adequate resolution density); a settled universe (3.U); residual alpha *after* factor/null attribution; a credible lookahead stance (placebo-primary verdict); deflated-Sharpe-positive under full-DoF N; cost-survivable; **and capacity-survivable on the settled universe `U`** (a live criterion if 3.U=B, automatically satisfied if 3.U=A). -> Phases 4-6.
**PIVOT** (real but mis-specified): re-spec, re-test.
**STOP** (no edge survives attribution + costs, OR density too sparse, OR forward-validation horizon infeasible, OR capacity insufficient on a broad `U`): archive as well-built infra.

**Standing decision:** a contaminated backtest is not allowed to manufacture a GO. If the placebo shows severe leakage, the honest gate is a forward paper-trading period (feasibility permitting), not a historical backtest.

**Acceptance:** a written validation report covering resolution density, the universe decision, the benchmark bar, the lookahead stance (placebo + corroboration) + power calc, attribution, capacity on `U`, and the GO/PIVOT/STOP call with evidence.

---

## Phases 4-6 - Conditional on a Phase-3 GO

Planned at task-level detail per the scope decision, but a STOP archives them and a PIVOT may reshape them.

### Phase 4 - Close the evaluation loop (M)
- Outcome-backfill job (T+N realized return -> `update_outcome`).
- Live metrics off the journal (hit rate, forward return by horizon, decay).
- Rolling monitor vs the validation baseline (alpha decay => retire, per house principle - not a refit trigger).

### Phase 5 - Knowledge-graph expansion (L)
- Implement highest-value generation paths from `KNOWLEDGE_GRAPH_PLAN_v1_2.md` (RSS -> EDGAR) beyond the semi seed.
- KG-coverage tests; version the graph; regenerate `watchlist.json`.
- If 3.U=A, the capacity concern (OQ-3) arrives here with small/mid-cap suppliers; if 3.U=B it was already handled at 3.6.
- Re-run a Phase-3 slice on the expanded universe before trusting it.

### Phase 6 - Homeguard integration and productionization (M-L)
- **Handoff contract semantics (OQ-7):** raw signal (ticker + action + confidence, Homeguard sizes) vs sized position. Pins what Scribe's outcome means (signal-level vs position-level). Signal is long-only today (`SignalAction` has no short) - confirm or extend. Inspect Homeguard's ingestion side to inform this.
- Define + version the Velites->Homeguard signal contract; validate against Homeguard ingestion.
- Ingestion mode: webhook receiver vs shared-storage file drop.
- **Scheduling supervision:** resolve in-app APScheduler vs systemd-timer-wrapped single-run (Homeguard consistency vs self-containment).
- **Operational monitoring** into the existing Discord + VictoriaMetrics/Grafana/Loki stack (run-completion / Scout-returned-data / dispatch-success). Structured logging is necessary but not alerting.
- Feature-flag live dispatch; mandatory paper/observation period before capital (mirror Homeguard gates).
- Finish D6 before 3.12 productionization.

---

## Critical path

```
Phase 0 (format-first) --+
                         +--> Phase 2 --> Phase 3 [GATE] --> { STOP | PIVOT->P3 | GO -> P4,P5,P6 }
Phase 1 ----------------+
   (0 & 1 parallel, S-effort; 1 rebases onto 0's format commit)

Phase 3 internal order (cheap-first; 3.P gates the historical era):
  3.0 density (recent) -> 3.U universe decision -> 3.1 price-only benchmark
  -> 3.P historical data build (ArXiv harvester [hard], Tiingo news, PIT prices)  [GATES below]
  -> 3.2 lookahead probe (placebo primary + dual-model corroboration) + power calc  [small slice]
  -> 3.3 grade cache + full corpus (causal hype baseline)
  -> 3.4 sweep (CPCV embargo >=20d+lag, full-DoF DSR)
  -> 3.5 residual attribution -> 3.6 cost/capacity -> 3.7 stability -> 3.8 survivorship
  -> report -> GATE
```

The two cheapest checks (3.0 density, 3.1 benchmark) and the universe decision precede the data build; the ArXiv harvester (3.P) is the gating prerequisite for everything historical and is the main reason Phase 3 is multiple-XL.

---

## Verification per phase

| Phase | Done means |
|---|---|
| 0 | 4 CI jobs green on clean checkout; `run_scheduled` imports in fresh venv |
| 1 | Cold-reader test passes from README + CLAUDE.md |
| 2 | `pytest tests/integration` green, zero live calls, no unexplained skips |
| 3 | Written validation report with the GO/PIVOT/STOP call + evidence (density, universe, lookahead, attribution, capacity) |
| 4-6 | Per-phase acceptance (conditional on GO) |

---

## Risks / contingencies (named explicitly)

1. **Resolution density too low/noisy (3.0)** - cheapest and earliest STOP; redirect to Phase 5 KG work. Density is measured against the full resolved entity set, not the assumed 11 semis.
2. **Universe fork unresolved (3.U)** - leaving it open silently changes what 3.1/3.5/3.6/3.8 even study; must be settled before those steps, and it flips whether capacity is a live gate criterion.
3. **Historical ArXiv harvester (3.P)** - unbudgeted, on the critical path, ArXiv-rate-limited; the single biggest reason Phase 3 is multiple-XL. Without it, 3.2/3.3 cannot run.
4. **Lookahead contamination invalidates the backtest premise (3.2)** - a feature, not a failure; routes to forward validation. The placebo (within-model, post-move) is primary because the dual-model differential confounds future-knowledge with capability. Forward validation's horizon may itself be infeasible (low-frequency signal) - the power calc can turn the fallback into a STOP.
5. **Sector beta dominates (3.1/3.5)** - the semi universe over the largest semi bull run will look brilliant for reasons unrelated to the thesis; attribution to *residual* alpha (not raw return) is non-negotiable.
6. **Survivorship via the data layer (3.1/3.8)** - a naive present-day price pull omits delisted/acquired names; require a PIT-correct universe snapshot and a named, adjusted price source.
7. **Under-deflated significance (3.4)** - if DSR N omits horizon/universe/logic/model DoF, the gate lies in the project's favor; N must be the full search cardinality.
8. **Non-causal hype baseline (3.3/3.4)** - the >3 sigma veto must use a trailing-only rolling window historically; a centered/full-sample window leaks future news.
9. **Old-cutoff model unavailable (3.2)** - named dependency for corroboration only; the placebo stands alone without it.

---

## Out of scope (from v2 plan)
- Module-architecture rewrite (ABC/adapter design is sound).
- Language/framework changes.
- Options/derivatives overlays (separate spec if the edge validates).
- Multi-asset KG beyond semis (deferred to conditional Phase 5).
- Production threshold auto-tuning (configurability is a research affordance, not license to retune live).
