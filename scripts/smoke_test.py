"""
Velites Smoke Test - End-to-end integration verification.

Verifies all modules work with live data before production deployment.

Usage:
    python scripts/smoke_test.py           # Full test with API calls
    python scripts/smoke_test.py --dry-run # Mock LLM calls (no cost)
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class SmokeTestResult:
    """Result of a single smoke test."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.details: dict = {}

    def success(self, message: str, **details) -> "SmokeTestResult":
        self.passed = True
        self.message = message
        self.details = details
        return self

    def failure(self, message: str, **details) -> "SmokeTestResult":
        self.passed = False
        self.message = message
        self.details = details
        return self


async def test_arxiv_fetcher() -> SmokeTestResult:
    """Test 1: ArxivFetcher returns valid papers."""
    result = SmokeTestResult("ArxivFetcher")

    try:
        from modules.scout import ArxivFetcher

        fetcher = ArxivFetcher()
        papers = await fetcher.fetch_papers(lookback_hours=72)

        if len(papers) == 0:
            return result.failure("No papers fetched", lookback_hours=72)

        sample = papers[0]
        return result.success(
            f"Fetched {len(papers)} papers",
            sample_title=sample.title[:60],
            sample_id=sample.id,
        )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_graph_engine() -> SmokeTestResult:
    """Test 2: GraphEngine loads knowledge graph."""
    result = SmokeTestResult("GraphEngine")

    try:
        from modules.mapper import GraphEngine

        engine = GraphEngine()
        engine.load_graph()

        # Test entity resolution
        text = "NVIDIA's new GPU uses TSMC's advanced process"
        entities = engine.resolve_text(text)

        if len(entities) == 0:
            return result.failure("No entities resolved from sample text")

        return result.success(
            f"Graph loaded, resolved {len(entities)} entities",
            sample_entity=entities[0].ticker,
            matched_term=entities[0].matched_term,
        )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_supply_chain() -> SmokeTestResult:
    """Test 3: SupplyChainNavigator finds dependencies."""
    result = SmokeTestResult("SupplyChainNavigator")

    try:
        from modules.mapper import GraphEngine, SupplyChainNavigator

        engine = GraphEngine()
        engine.load_graph()
        nav = SupplyChainNavigator(engine)

        deps = nav.get_dependencies("NVDA")

        return result.success(
            f"Found dependencies for NVDA",
            tier1_suppliers=deps.tier1_suppliers[:3],
            customers=deps.customers[:3],
        )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_llm_agent(dry_run: bool = False) -> SmokeTestResult:
    """Test 4: LLMAgent can call API (or mock in dry-run)."""
    result = SmokeTestResult("LLMAgent")

    try:
        from config import settings

        if dry_run:
            return result.success("Skipped (dry-run mode)", api_key_set=bool(settings.openai_api_key or settings.anthropic_api_key))

        if not settings.openai_api_key and not settings.anthropic_api_key:
            return result.failure("No API key configured", hint="Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")

        from modules.analyst import LLMAgent

        agent = LLMAgent()
        score = await agent.grade_innovation(
            text="Novel GPU architecture achieves 2x transformer inference performance.",
            ticker="NVDA",
            ticker_context="GPU Designer",
            paper_id="smoke_test_001",
        )

        return result.success(
            f"LLM graded innovation: {score.score:.2f}",
            reasoning=score.reasoning[:80],
        )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_sentiment_engine(dry_run: bool = False) -> SmokeTestResult:
    """Test 5: SentimentEngine loads FinBERT model."""
    result = SmokeTestResult("SentimentEngine")

    try:
        if dry_run:
            # Check if transformers is installed
            try:
                import transformers
                return result.success("Skipped (dry-run mode)", transformers_version=transformers.__version__)
            except ImportError:
                return result.failure("transformers not installed", hint="pip install transformers torch")

        from modules.scout.models import NewsObject
        from modules.analyst import SentimentEngine

        engine = SentimentEngine()

        news = [
            NewsObject(
                id="test_1",
                headline="NVIDIA Reports Record Revenue Driven by AI Demand",
                summary="Strong quarterly results...",
                source="Test",
                url="https://example.com",
                timestamp=datetime.now(timezone.utc),
                tickers=["NVDA"],
                keywords=[],
            ),
        ]

        sentiment = await engine.analyze_sentiment(news, "NVDA")

        return result.success(
            f"Sentiment score: {sentiment.score:.2f}",
            hype_volume=sentiment.hype_volume,
            is_veto=sentiment.is_veto,
        )
    except ImportError:
        return result.failure("transformers/torch not installed", hint="pip install transformers torch")
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_dispatcher() -> SmokeTestResult:
    """Test 6: Dispatcher works in file mode."""
    result = SmokeTestResult("Dispatcher")

    try:
        import tempfile
        from modules.courier import Dispatcher
        from modules.courier.models import AlphaSignal, SignalAction

        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = Dispatcher()
            dispatcher.webhook_url = ""  # Force file mode
            dispatcher.output_dir = Path(tmpdir)

            signal = AlphaSignal(
                signal_id="velites_smoke_test",
                action=SignalAction.BUY_LONG,
                ticker="NVDA",
                confidence=0.85,
                reasoning="Smoke test signal",
                valid_until=datetime.now(timezone.utc) + timedelta(hours=24),
            )

            dispatch_result = await dispatcher.dispatch(signal)

            files = list(Path(tmpdir).glob("*.json"))
            if not files:
                return result.failure("No signal file created")

            return result.success(
                f"Signal dispatched to file",
                file_name=files[0].name,
            )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_journal() -> SmokeTestResult:
    """Test 7: Journal works with in-memory SQLite."""
    result = SmokeTestResult("Journal")

    try:
        from modules.scribe import Journal
        from modules.courier.models import AlphaSignal, SignalAction

        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        await journal.initialize()

        signal = AlphaSignal(
            signal_id="velites_smoke_test_journal",
            action=SignalAction.BUY_LONG,
            ticker="NVDA",
            confidence=0.9,
            reasoning="Smoke test journal entry",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        record_id = await journal.record_signal(signal, 500.0)

        signals = await journal.get_signals_for_backtest()
        stats = await journal.get_signal_stats()

        return result.success(
            f"Journal recorded signal: {record_id}",
            total_signals=stats["total_signals"],
        )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def test_news_fetcher() -> SmokeTestResult:
    """Test 8: NewsFetcher fetches RSS news."""
    result = SmokeTestResult("NewsFetcher")

    try:
        from modules.scout import NewsFetcher

        fetcher = NewsFetcher()
        news = await fetcher.fetch_from_rss()

        if len(news) == 0:
            return result.failure("No news fetched from RSS")

        return result.success(
            f"Fetched {len(news)} news items",
            sample_headline=news[0].headline[:60] if news else "N/A",
        )
    except Exception as e:
        return result.failure(f"Exception: {e}")


async def run_all_tests(dry_run: bool = False) -> list[SmokeTestResult]:
    """Run all smoke tests."""
    print("\n" + "=" * 70)
    print("VELITES SMOKE TEST")
    print("=" * 70)
    if dry_run:
        print("[!] Running in DRY-RUN mode (LLM/Sentiment calls skipped)")
    print()

    results: list[SmokeTestResult] = []

    tests = [
        ("1/8", "ArxivFetcher", test_arxiv_fetcher()),
        ("2/8", "NewsFetcher", test_news_fetcher()),
        ("3/8", "GraphEngine", test_graph_engine()),
        ("4/8", "SupplyChainNavigator", test_supply_chain()),
        ("5/8", "LLMAgent", test_llm_agent(dry_run)),
        ("6/8", "SentimentEngine", test_sentiment_engine(dry_run)),
        ("7/8", "Dispatcher", test_dispatcher()),
        ("8/8", "Journal", test_journal()),
    ]

    for num, name, coro in tests:
        print(f"[{num}] Testing {name}...")
        result = await coro
        results.append(result)

        if result.passed:
            print(f"      [+] {result.message}")
            for key, value in result.details.items():
                print(f"          {key}: {value}")
        else:
            print(f"      [-] FAILED: {result.message}")
            for key, value in result.details.items():
                print(f"          {key}: {value}")
        print()

    # Summary
    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r.passed:
                print(f"  [-] {r.name}: {r.message}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Velites Smoke Test")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM and Sentiment API calls (no cost)",
    )
    args = parser.parse_args()

    results = asyncio.run(run_all_tests(dry_run=args.dry_run))

    # Exit with error code if any test failed
    failed = sum(1 for r in results if not r.passed)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
