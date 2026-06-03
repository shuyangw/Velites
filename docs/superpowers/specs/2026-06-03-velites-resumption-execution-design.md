# Velites Resumption - Execution Design Spec

**Date:** 2026-06-03
**Status:** PROPOSED (awaiting user review)
**Source plan:** `20260602_velites_resumption_plan_v2.md` (to be committed to `docs/planning/20260602_velites_resumption_plan.md` in Phase 1)
**Scope decision:** Plan all 6 phases at task-level detail. Phases 4-6 are tagged conditional on a Phase-3 GO.

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
| **Watchlist scope** | **CONFIRMED: no watchlist filter in the resolution->signal path.** `GraphEngine.resolve_text` (`graph_engine.py:140`) matches the full company-alias set + the entire `product_map` (cloud, AI models, cybersecurity, consumer electronics - beyond the 11 semis). `main.py:151` takes `primary = max(entities, key=confidence)` and emits on `primary.ticker` with no watchlist gate. Configured `watchlist_path` (`config.py:29`) is defined but unreferenced. The pipeline can emit off-watchlist signals today; the plan's "11-name universe" is not what the pipeline produces. |

---

## Execution approach

**Chosen: sequential, gate-respecting.** Mirror the plan's critical path - Phases 0 and 1 in parallel (cheap, independent) -> Phase 2 -> **Phase 3 gate** -> 4/5/6 on GO. Within Phase 3, run the cheapest kill-checks first (resolution density, price-only benchmark) before the contamination probe, and all of those before the expensive corpus build, so the most likely STOP reasons surface for the least effort.

Rejected alternatives:
- **Defect-batched** (land all D2-D9 first ignoring phase boundaries): faster to CI-green but tangles Phase-0 CI fixes with Phase-1 docs and loses the phase narrative.
- **Risk-first** (jump to Phase-3 probes before Phase 2): front-loads the verdict but runs the probes on an un-CI-verified DAG, weakening trust in the results. We borrow only its idea of ordering cheap probes early - inside Phase 3, not ahead of CI hygiene.

### Branch / commit / PR structure

- One branch + PR per phase; atomic commits (one logical unit each) per repo convention.
- **Phase 0's `ruff format` commit lands first; all other branches rebase onto it** to avoid reformat churn across parallel work. Phase 1 (parallel) rebases onto the format commit, not raw `main`.
- No pushing without explicit user approval (house rule).
- Phase 3 research artifacts live under `docs/` (or a research dir), NOT shipped to `main` as product code - with one exception: the **grade cache (3.3) is ship-quality infra and lands in `main`** behind the module structure.
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
5. **Surface the watchlist-scope finding** (from Verified Current State) as a documented decision item for Phase 3.0: is off-watchlist signal emission intended, or is the watchlist filter a missing gate?

**Acceptance:** a cold reader can state the thesis, data flow, and run commands from README + CLAUDE.md.

---

## Phase 2 - Promote smoke test into CI-gated integration coverage (S-M)

Branch `phase-2-integration`.

1. Confirm `smoke_test.py --dry-run` runs the full DAG with mocked LLM/sentiment and **zero live calls**.
2. Extract its core into `tests/integration/test_pipeline.py`, replacing the 2 skipped stubs, so Scout->Scribe is CI-verified.
3. Audit the skipped tests (the +2 are inverted dependency-absent guards per OQ-5; confirm intentional, not silent coverage loss).

**Acceptance:** `pytest tests/integration` exercises Scout->Scribe with zero live calls; no unexplained skips.

---

## Phase 3 - Signal validation study (GATE: STOP / PIVOT / GO) (L-XL)

Branch `phase-3-validation`. Research artifacts under `docs/` except the grade cache (3.3), which is ship-quality and lands in `main`.

**Ordering principle: cheapest kill-checks first.** Two checks that need no grading and (3.0) no API spend precede even the contamination probe, because they can kill the project for the least effort.

### 3.0 Resolution-density check (NEW - first; zero API spend; can STOP)
Run `GraphEngine.resolve_text` over a historical ArXiv sample. Measure:
- **Resolution fraction** - what share of abstracts resolve to any ticker. ArXiv abstracts describe methods ("a diffusion transformer for..."), not products/tickers, so resolution may fire too rarely (signal too sparse to validate) or too loosely (generic terms -> noise).
- **Semantic soundness** - spot-check that resolutions are real, not coincidental substring hits.
- Measured against the **full KG entity set**, not just the 11 semis (per the watchlist-scope finding).
- Report the watchlist scope decision: intended off-watchlist emission, or a missing filter.

**Kill condition:** if density is too sparse or too noisy to support validation, STOP or redirect to Phase 5 KG work before any grading.

### 3.1 Price-only benchmark bar (early; pure price data; no corpus)
Establish the bar the signal must clear, using only price data:
- Buy-and-hold the universe (sector beta).
- Plain cross-sectional momentum on the same universe.

In this period plain semi momentum is likely already deflated-Sharpe-positive, which reframes the question to "does innovation-lag add **residual** alpha on top of that." (Signal-vs-baseline *attribution* is deferred to 3.5, since it needs the signal.)

### 3.2 Lookahead contamination probe (dual-model cutoff differential)
The "contemporaneously-graded holdout" is not executable - Velites was not running historically, so no contemporaneous grades exist. Clean instantiation:
- Grade the same historical papers with (i) a **current frontier model** (knows how the tech/ticker played out) and (ii) a model whose **training cutoff predates each paper** (cannot know).
- The **gap in their forward-return predictiveness is the contamination magnitude.**

**Named dependency:** an accessible old-cutoff model. **Fallback if none exists:** a weaker placebo - test whether scores "predict" returns for papers published *after* the move - or default to forward validation on priors.

**Forward-validation feasibility (power calculation) - part of this step, not deferred:** the signal is low-frequency (a few resolved papers/week). Given expected signals/week and a hypothesized per-signal effect, compute how long a forward period must run to reach significance. **An ~18-month answer is itself a decision-relevant finding (potential STOP), not an implementation detail.** Forward validation is not a free fallback.

**Branch on the probe:**
- Small gap -> historical backtest is valid for the full signal.
- Large gap -> the innovation score is gated by a forward paper-trading period (feasibility per the power calc); historical replay is used only for the less-contaminated parts (threshold/cost/portfolio sensitivity).

### 3.3 Grade cache (SHIP-QUALITY -> main) + historical corpus build
- **Grade cache:** persist `InnovationScore` + `SentimentScore` keyed by `(paper_id, model, prompt_version)`, so threshold replay reads cached grades and costs nothing per sweep. Build it to land in `main` behind the module structure (on a GO it caches grades live for reproducibility and to avoid re-grading). This is the precondition that makes the sweep affordable.
- **Historical corpus:** ArXiv submission timestamp = causal; point-in-time Tiingo news (filter on availability time `publishedDate`/`crawlDate`, guard publication-vs-ingestion leakage - OQ-1); forward returns at 1d/5d/20d on the resolved universe; persisted via `save_enriched.py` format.

### 3.4 Threshold sweep wrapped in a proper protocol
Use `replay_signals.py` for the sweep, but wrap it:
- **Walk-forward + CPCV** with purge/embargo over the news/price overlap.
- **Embargo pinned numerically: >= max label horizon + news-availability lag.** With overlapping 20-day forward labels, **embargo >= 20d + lag**, stated explicitly so it cannot be under-embargoed (adjacent samples share outcome windows and leak otherwise).
- **Deflated / probabilistic Sharpe to pay for the search. Trial count N = the FULL researcher DoF**, not just the threshold grid: thresholds x horizons (1/5/20d) x universe definition x confluence-logic variants x model choice. Scoping N to the threshold sweep under-counts trials, under-deflates, and overstates significance (the Lopez de Prado failure mode).

### 3.5 Residual attribution (needs the signal)
Attribute returns to market + sector + momentum (+ size, given MU/INTC dispersion) and report **residual alpha, not raw return**, against the 3.1 bar and a shuffled-timestamp / shuffled-paper null. Direct echo of the Homeguard finding that plain momentum beat the regime overlay: plain sector exposure may beat the innovation signal.

### 3.6-3.8 Supporting checks
- **3.6 Cost model + capacity:** empirical spreads (not heuristic tiers); the 11-name primary universe is mega/large-cap so capacity is a non-issue here (OQ-3) - capacity concern attaches to small/mid-cap KG suppliers at Phase 5.
- **3.7 Threshold-stability map** (0.7 / -0.5 / 3 sigma): plateau vs cherry-pick.
- **3.8 Survivorship check** on the universe (semi delistings / M&A).

### GATE decision
**GO** requires: passing 3.0 (adequate resolution density); residual alpha *after* factor/null attribution; a credible answer to the lookahead stance; deflated-Sharpe-positive under full-DoF N; cost-survivable; sane capacity. -> Phases 4-6.
**PIVOT** (real but mis-specified): re-spec, re-test.
**STOP** (no edge survives attribution + costs, OR density too sparse, OR forward-validation horizon infeasible): archive as well-built infra.

**Standing decision:** a contaminated backtest is not allowed to manufacture a GO. If lookahead is severe, the honest gate is a forward paper-trading period (feasibility permitting), not a historical backtest.

**Acceptance:** a written validation report covering resolution density, the benchmark bar, the lookahead stance + power calc, attribution, and the GO/PIVOT/STOP call with evidence.

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
- Capacity concern (OQ-3) arrives here with small/mid-cap suppliers (e.g. PLAB, UCTT).
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

Phase 3 internal order (cheap-first):
  3.0 density -> 3.1 benchmark bar -> 3.2 lookahead probe+power calc
  -> 3.3 grade cache + corpus -> 3.4 sweep (CPCV, full-DoF DSR) -> 3.5 residual attribution
  -> 3.6 cost / 3.7 stability / 3.8 survivorship -> report -> GATE
```

The two cheapest checks (3.0 density, 3.1 benchmark) precede even the contamination probe, because they can kill the project for the least effort. The grade cache is the precondition that makes the sweep affordable.

---

## Verification per phase

| Phase | Done means |
|---|---|
| 0 | 4 CI jobs green on clean checkout; `run_scheduled` imports in fresh venv |
| 1 | Cold-reader test passes from README + CLAUDE.md |
| 2 | `pytest tests/integration` green, zero live calls, no unexplained skips |
| 3 | Written validation report with the GO/PIVOT/STOP call + evidence |
| 4-6 | Per-phase acceptance (conditional on GO) |

---

## Risks / contingencies (named explicitly)

1. **Resolution density too low/noisy (3.0)** - cheapest and earliest STOP; redirect to Phase 5 KG work. The pipeline's lack of a watchlist filter means resolution targets a broader entity set than assumed; density must be measured against reality.
2. **Lookahead contamination invalidates the backtest premise (3.2)** - a feature, not a failure; plan routes to forward validation. But forward validation's horizon may itself be infeasible (low-frequency signal) - the power calc can turn the fallback into a STOP.
3. **Sector beta dominates (3.1/3.5)** - the 11-name semi universe over the largest semi bull run will look brilliant for reasons unrelated to the thesis; attribution to *residual* alpha (not raw return) is non-negotiable.
4. **Under-deflated significance (3.4)** - if DSR N omits horizon/universe/logic/model DoF, the gate lies in the project's favor; N must be the full search cardinality.
5. **Old-cutoff model unavailable (3.2)** - named dependency; fallback is a weaker placebo or forward-on-priors.

---

## Out of scope (from v2 plan)
- Module-architecture rewrite (ABC/adapter design is sound).
- Language/framework changes.
- Options/derivatives overlays (separate spec if the edge validates).
- Multi-asset KG beyond semis (deferred to conditional Phase 5).
- Production threshold auto-tuning (configurability is a research affordance, not license to retune live).
