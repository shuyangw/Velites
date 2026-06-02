"""
Replay Signals - Regenerate signals from saved enriched papers.

Allows fast iteration on ConfluenceEngine thresholds without
re-fetching data from ArXiv and running LLM calls.

Usage:
    python scripts/replay_signals.py --input data/enriched_20260117.json
    python scripts/replay_signals.py --input data/enriched.json --innovation-threshold 0.6
    python scripts/replay_signals.py --input data/enriched.json --hype-threshold 2.5 --dry-run
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def load_enriched_papers(input_path: Path) -> list[dict]:
    """Load enriched papers from JSON file."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = data.get("papers", [])
    logger.info("loaded_enriched_papers", count=len(papers), run_id=data.get("run_id"))
    return papers


async def generate_signals(
    enriched_papers: list[dict],
    innovation_threshold: float,
    sentiment_veto_threshold: float,
    hype_threshold: float,
    dry_run: bool = False,
) -> list[dict]:
    """Generate signals from enriched papers with custom thresholds."""
    from modules.scout import NewsFetcher
    from modules.scout.models import PaperObject
    from modules.analyst import LLMAgent, SentimentEngine, ConfluenceEngine
    from modules.analyst.models import InnovationScore, SentimentScore
    from modules.courier.models import SignalAction

    # Initialize components
    confluence_engine = ConfluenceEngine(
        innovation_threshold=innovation_threshold,
        sentiment_veto_threshold=sentiment_veto_threshold,
        hype_threshold=hype_threshold,
    )

    # Instantiate analysis clients once (FinBERT load is expensive); dry-run skips them
    llm_agent = None
    sentiment_engine = None
    news_fetcher = None
    if not dry_run:
        llm_agent = LLMAgent()
        sentiment_engine = SentimentEngine()
        news_fetcher = NewsFetcher()

    results = []

    for item in enriched_papers:
        paper_data = item["paper"]
        ticker = item["primary_ticker"]

        # In dry-run mode, create mock scores
        if dry_run:
            innovation = InnovationScore(
                score=0.75,  # Mock score
                reasoning="[DRY-RUN] Mock innovation score",
                ticker=ticker,
                paper_id=paper_data.get("id", "unknown"),
            )
            sentiment = SentimentScore(
                score=0.1,  # Mock score
                hype_volume=0.5,  # Mock hype
                is_veto=False,
                ticker=ticker,
            )
        else:
            # Grade innovation
            innovation = await llm_agent.grade_innovation(
                text=paper_data.get("abstract", ""),
                ticker=ticker,
                ticker_context=f"{ticker} from knowledge graph",
                paper_id=paper_data.get("id", "unknown"),
            )

            # Fetch news and analyze sentiment
            news = await news_fetcher.fetch_news([ticker])
            sentiment = await sentiment_engine.analyze_sentiment(news, ticker)

        # Generate confluence signal
        signal = confluence_engine.generate_signal(
            ticker=ticker,
            innovation=innovation,
            sentiment=sentiment,
            source_type="arxiv",
        )

        results.append({
            "ticker": ticker,
            "paper_title": paper_data.get("title", "")[:60],
            "action": signal.action.value,
            "confidence": signal.confidence,
            "innovation_score": innovation.score,
            "sentiment_score": sentiment.score,
            "hype_volume": sentiment.hype_volume,
            "reasoning": signal.reasoning[:80] if signal.reasoning else "",
        })

    return results


def format_results(results: list[dict], thresholds: dict) -> str:
    """Format results as ASCII table."""
    lines = [
        "=" * 100,
        "REPLAY RESULTS",
        f"Thresholds: innovation={thresholds['innovation']:.2f}, "
        f"sentiment_veto={thresholds['sentiment_veto']:.2f}, "
        f"hype={thresholds['hype']:.2f}",
        "=" * 100,
        "",
    ]

    # Group by action
    by_action = {}
    for r in results:
        action = r["action"]
        if action not in by_action:
            by_action[action] = []
        by_action[action].append(r)

    # Summary
    lines.append("SUMMARY:")
    for action, items in sorted(by_action.items()):
        lines.append(f"  {action}: {len(items)}")
    lines.append("")

    # Table header
    lines.append(f"{'Ticker':<8} {'Action':<10} {'Conf':<6} {'Innov':<6} {'Sent':<6} {'Hype':<6} {'Title':<40}")
    lines.append("-" * 100)

    # Table rows
    for r in results:
        lines.append(
            f"{r['ticker']:<8} "
            f"{r['action']:<10} "
            f"{r['confidence']:.2f}   "
            f"{r['innovation_score']:.2f}   "
            f"{r['sentiment_score']:.2f}   "
            f"{r['hype_volume']:.2f}   "
            f"{r['paper_title'][:40]}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Replay signals with custom thresholds")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to enriched papers JSON file",
    )
    parser.add_argument(
        "--innovation-threshold",
        type=float,
        default=0.7,
        dest="innovation_threshold",
        help="Innovation score threshold (default: 0.7)",
    )
    parser.add_argument(
        "--sentiment-veto-threshold",
        type=float,
        default=-0.5,
        dest="sentiment_veto_threshold",
        help="Sentiment veto threshold (default: -0.5)",
    )
    parser.add_argument(
        "--hype-threshold",
        type=float,
        default=3.0,
        dest="hype_threshold",
        help="Hype volume threshold in std devs (default: 3.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock scores instead of calling LLM/sentiment APIs",
    )
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILE",
        help="Export results to JSON file",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("VELITES - REPLAY SIGNALS")
    print(f"{'=' * 60}")
    if args.dry_run:
        print("[!] Running in DRY-RUN mode (mock scores)")
    print()

    # Load enriched papers
    enriched_papers = load_enriched_papers(input_path)

    if not enriched_papers:
        print("No enriched papers found in input file.")
        sys.exit(1)

    # Generate signals
    results = asyncio.run(generate_signals(
        enriched_papers,
        innovation_threshold=args.innovation_threshold,
        sentiment_veto_threshold=args.sentiment_veto_threshold,
        hype_threshold=args.hype_threshold,
        dry_run=args.dry_run,
    ))

    # Format and print results
    thresholds = {
        "innovation": args.innovation_threshold,
        "sentiment_veto": args.sentiment_veto_threshold,
        "hype": args.hype_threshold,
    }
    print(format_results(results, thresholds))

    # Export if requested
    if args.export:
        export_data = {
            "thresholds": thresholds,
            "dry_run": args.dry_run,
            "results": results,
        }
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
        print(f"\n[+] Results exported to: {args.export}")


if __name__ == "__main__":
    main()
