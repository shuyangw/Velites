"""
Save Enriched Papers - Captures pipeline state after entity resolution.

Runs the Scout + Mapper steps and saves enriched papers to JSON
for later replay with different confluence thresholds.

Usage:
    python scripts/save_enriched.py --output data/enriched_20260117.json
    python scripts/save_enriched.py  # Auto-generates timestamped filename
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


async def run_ingestion_and_resolution():
    """Run Scout + Mapper steps and return enriched papers."""
    from modules.scout import ArxivFetcher
    from modules.mapper import GraphEngine, SupplyChainNavigator

    # Scout
    logger.info("step_1_ingestion_start")
    arxiv_fetcher = ArxivFetcher()
    papers = await arxiv_fetcher.fetch_papers()
    papers = arxiv_fetcher.filter_generic_papers(papers)
    logger.info("step_1_ingestion_complete", paper_count=len(papers))

    if not papers:
        return []

    # Mapper
    logger.info("step_2_entity_resolution_start")
    graph_engine = GraphEngine()
    graph_engine.load_graph()
    supply_chain = SupplyChainNavigator(graph_engine)

    enriched = []
    for paper in papers:
        text = f"{paper.title} {paper.abstract}"

        # Resolve entities
        entities = graph_engine.resolve_text(text)
        if not entities:
            continue

        # Get primary ticker
        primary = max(entities, key=lambda e: e.confidence)

        # Get supply chain dependencies (may fail for tickers not in graph)
        try:
            dependencies = supply_chain.get_dependencies(primary.ticker)
            dependencies_dict = dependencies.model_dump(mode="json")
        except Exception as e:
            logger.debug("supply_chain_lookup_failed", ticker=primary.ticker, error=str(e))
            dependencies_dict = None

        enriched.append({
            "paper": paper.model_dump(mode="json"),
            "primary_ticker": primary.ticker,
            "entities": [e.model_dump(mode="json") for e in entities],
            "dependencies": dependencies_dict,
        })

    logger.info("step_2_entity_resolution_complete", enriched_count=len(enriched))
    return enriched


def main():
    parser = argparse.ArgumentParser(description="Save enriched papers for replay")
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: auto-generated)",
    )
    args = parser.parse_args()

    # Generate output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = Path("data") / f"enriched_{timestamp}.json"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run pipeline
    print(f"\n{'=' * 60}")
    print("VELITES - SAVE ENRICHED PAPERS")
    print(f"{'=' * 60}\n")

    enriched = asyncio.run(run_ingestion_and_resolution())

    if not enriched:
        print("No papers were enriched. Check ArXiv connectivity.")
        sys.exit(1)

    # Create output structure
    output = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(enriched),
        "papers": enriched,
    }

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n[+] Saved {len(enriched)} enriched papers to: {output_path}")
    print("\nSample tickers found:")
    for item in enriched[:5]:
        print(f"  - {item['primary_ticker']}: {item['paper']['title'][:50]}...")


if __name__ == "__main__":
    main()
