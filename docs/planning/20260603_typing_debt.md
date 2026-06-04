# Typing Debt - 2026-06-03

## Background

During Phase 0 repo rehabilitation, mypy strict mode was relaxed on 2026-06-03.
Strict was never enforced before this date (CI pointed at a dead path `src/velites`).
When the path was corrected to `src`, mypy reported 88 errors in 22 files under strict.

Decision: relax strict, record the debt, restore incrementally module-by-module.

## Original Error Count

88 errors in 22 files under `strict = true`.

## Category Breakdown

### 1. VelitesError subclassing across 5 modules (5 errors - RESOLVED via mypy_path fix)

`Class cannot subclass "VelitesError" (has type "Any")` appeared in:
- `modules/scribe/exceptions.py`
- `modules/scout/exceptions.py`
- `modules/mapper/exceptions.py`
- `modules/courier/exceptions.py`
- `modules/analyst/exceptions.py`

Root cause: `from exceptions import VelitesError` was resolving to the wrong `config`
module because `src/` was not on `mypy_path`. Fixed by adding `mypy_path = "src"`,
`explicit_package_bases = true`, `namespace_packages = true` to `[tool.mypy]`.

### 2. config attr-defined errors (4 errors in src/__init__.py + 8 in module files - RESOLVED)

`Module "config" has no attribute "settings"/"Settings"/"get_settings"` in 9 files.
Same root cause as above - mypy was not finding `src/config.py`. Fixed by `mypy_path = "src"`.

### 3. mapper module JSON dict typing (~18 errors - DEFERRED via ignore_errors override)

`modules/mapper/graph_engine.py`, `ticker_normalizer.py`, `supply_chain.py` operate over
untyped JSON dicts loaded from knowledge graph files. networkx node data is `Any`.
Errors: `union-attr` on chained `.get()` calls, `assignment` of `Any | None` to `str`,
`var-annotated` for `results = []`, `no-any-return` from networkx operations.

Suppressed via `ignore_errors = true` override. Restore plan: type the JSON loading
with `TypedDict` or `dict[str, Any]` annotations and add explicit guards.

### 4. SQLAlchemy Column vs Python type mismatches (5 errors in journal.py - RESOLVED via type: ignore)

SQLAlchemy 2.x Column stubs report `Column[T]` vs plain Python types on model attribute
assignment and use as dict keys. Affected: `record.outcome_price`, `record.outcome_date`,
`r.ticker` used as dict key/index. Annotated with `# type: ignore[assignment/index/arg-type]`.

### 5. feedparser time_struct unpacking (2 errors in arxiv_fetcher.py - RESOLVED via type: ignore)

`datetime(*entry.updated_parsed[:6], tzinfo=UTC)` triggers `[misc]` because feedparser
stubs type `time_struct` as having `tzinfo` at position 8, making mypy think `tzinfo` is
passed twice. Added `# type: ignore[misc]` with justification.

### 6. Anthropic SDK union type (5 errors in llm_agent.py - RESOLVED via type: ignore)

`response.content[0].text` triggers `union-attr` because `content[0]` is typed as
`TextBlock | ThinkingBlock | RedactedThinkingBlock | ToolUseBlock | ...`. In practice
non-tool calls always return a `TextBlock`. Added `# type: ignore[union-attr]`.

### 7. sentiment_engine lazy-init None pattern (4 errors - RESOLVED via Any annotation)

`self._model` and `self._tokenizer` initialized to `None`, then used after `load_model()`.
Typed as `Any` to allow the late-binding pattern. Restore plan: use `Optional[AutoModel]`
with proper guards or restructure to require `load_model()` before first use.

### 8. news_fetcher override incompatibility (1 error - RESOLVED via type: ignore)

`NewsFetcher.fetch_news` adds `use_tiingo: bool` parameter not in `BaseNewsFetcher`.
Also `lookback_hours` narrowed from `int | None` to `int`. Added `# type: ignore[override]`.
Restore plan: align the base class signature with the concrete implementation.

### 9. httpx params dict[str, object] (1 error in news_fetcher.py - RESOLVED)

Mixed `str` and `int` values in the params dict inferred as `dict[str, object]`.
Fixed by annotating as `dict[str, str | int]`.

### 10. strict-only errors removed by relaxation (~48 errors)

Under non-strict baseline (no `disallow_untyped_defs`, `warn_return_any`, etc.):
- `no-untyped-def` / `no-untyped-call` in main.py, sentiment_engine.py (~15 errors)
- `no-any-return` spread across mapper and other files (~20 errors)
- `type-arg` (missing generic type args on bare `dict`) in mapper, scribe (~13 errors)
These are now deferred to the strict-restore phase.

## Restore Plan

Restore `strict = true` incrementally by module, one commit per module:

1. `modules/courier/` - clean architecture, straightforward to annotate
2. `modules/scout/` - fix base/subclass signature, annotate fetchers
3. `modules/scribe/` - resolve SQLAlchemy Column stubs fully
4. `modules/analyst/` - type Anthropic response content, fix lazy-init pattern
5. `modules/mapper/` - biggest effort; type the JSON graph with TypedDict
6. `src/main.py`, `config.py`, `logging_config.py` - top-level files last

Remove `ignore_errors = true` overrides as each module is cleaned up.

## Current Non-Strict Config

```toml
[tool.mypy]
python_version = "3.11"
warn_unused_ignores = true
plugins = ["pydantic.mypy"]
mypy_path = "src"
explicit_package_bases = true
namespace_packages = true
```

With `ignore_errors = true` overrides on `modules.mapper.graph_engine`,
`modules.mapper.ticker_normalizer`, and `modules.mapper.supply_chain`.
