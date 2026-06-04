"""
Velites Main Orchestrator

The Event Loop that coordinates all modules in a DAG workflow.
Supports both single-run mode and scheduled execution via APScheduler.

Usage:
    python -m src.main                  # Single run (default)
    python -m src.main --mode scheduled # Scheduled execution every 4 hours
    python -m src.main --mode single    # Explicit single run
"""

import argparse
import asyncio
import signal
import sys
from datetime import UTC, datetime

from config import settings
from logging_config import configure_logging, get_logger
from modules.analyst import ConfluenceEngine, LLMAgent, SentimentEngine
from modules.courier import Dispatcher, LiquidityGuard
from modules.courier.models import AlphaSignal, SignalAction
from modules.mapper import GraphEngine, SupplyChainNavigator, TickerNormalizer

# Module imports
from modules.scout import ArxivFetcher, MarketFetcher, NewsFetcher
from modules.scribe import Journal

logger = get_logger(__name__)


class VelitesOrchestrator:
    """
    Main orchestrator for the Velites research pipeline.

    Workflow:
    1. Scout: Fetch papers, news, market data
    2. Mapper: Resolve entities, map supply chain
    3. Analyst: Grade innovation, analyze sentiment, generate signals
    4. Courier: Validate liquidity, dispatch to Homeguard
    5. Scribe: Record signals for backtesting
    """

    def __init__(self) -> None:
        # Scout
        self.arxiv_fetcher = ArxivFetcher()
        self.news_fetcher = NewsFetcher()
        self.market_fetcher = MarketFetcher()

        # Mapper
        self.graph_engine = GraphEngine()
        self.supply_chain = SupplyChainNavigator(self.graph_engine)
        self.ticker_normalizer = TickerNormalizer(self.graph_engine)

        # Analyst
        self.llm_agent = LLMAgent()
        self.sentiment_engine = SentimentEngine()
        self.confluence_engine = ConfluenceEngine()

        # Courier
        self.dispatcher = Dispatcher()
        self.liquidity_guard = LiquidityGuard()

        # Scribe
        self.journal = Journal()

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("initializing_velites")

        # Load knowledge graph
        self.graph_engine.load_graph()

        # Initialize journal
        await self.journal.initialize()

        logger.info("velites_initialized")

    async def run_pipeline(self) -> list[AlphaSignal]:
        """
        Run the complete Velites pipeline.

        Returns:
            List of generated signals
        """
        run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        logger.info("starting_pipeline_run", run_id=run_id)

        signals: list[AlphaSignal] = []

        try:
            # Step 1: Ingestion
            papers = await self._step_ingestion()
            if not papers:
                logger.info("no_papers_found", run_id=run_id)
                return signals

            # Step 2: Entity Resolution
            enriched_papers = await self._step_entity_resolution(papers)
            if not enriched_papers:
                logger.info("no_entities_resolved", run_id=run_id)
                return signals

            # Step 3: Signal Generation
            raw_signals = await self._step_signal_generation(enriched_papers)

            # Step 4: Liquidity Check & Dispatch
            signals = await self._step_dispatch(raw_signals)

            # Log run summary
            logger.info(
                "pipeline_run_complete",
                run_id=run_id,
                signals_generated=len(signals),
                signals_dispatched=[
                    {
                        "ticker": s.ticker,
                        "action": s.action.value,
                        "confidence": round(s.confidence, 2),
                    }
                    for s in signals
                ],
            )

        except Exception as e:
            logger.error("pipeline_run_failed", run_id=run_id, error=str(e))
            raise

        return signals

    async def _step_ingestion(self) -> list[dict]:
        """Step 1: Fetch and normalize raw data."""
        logger.info("step_ingestion_start")

        # Fetch ArXiv papers
        papers = await self.arxiv_fetcher.fetch_papers()
        papers = self.arxiv_fetcher.filter_generic_papers(papers)

        logger.info("step_ingestion_complete", paper_count=len(papers))
        return [{"paper": p, "type": "PAPER"} for p in papers]

    async def _step_entity_resolution(self, items: list[dict]) -> list[dict]:
        """Step 2: Resolve entities and enrich with supply chain data."""
        logger.info("step_entity_resolution_start", item_count=len(items))

        enriched = []
        skipped_no_entities = 0

        for item in items:
            paper = item["paper"]
            text = f"{paper.title} {paper.abstract}"

            # Resolve entities
            entities = self.graph_engine.resolve_text(text)
            if not entities:
                skipped_no_entities += 1
                logger.debug(
                    "paper_no_entities",
                    paper_id=paper.id,
                    title=paper.title[:80],
                )
                continue

            # Get primary ticker
            primary = max(entities, key=lambda e: e.confidence)
            all_tickers = [e.ticker for e in entities]

            logger.info(
                "paper_entities_resolved",
                paper_id=paper.id,
                title=paper.title[:60],
                primary_ticker=primary.ticker,
                all_tickers=all_tickers[:5],  # Limit to first 5
                confidence=round(primary.confidence, 2),
            )

            # Get supply chain dependencies (may fail for tickers not in graph)
            try:
                dependencies = self.supply_chain.get_dependencies(primary.ticker)
            except Exception as e:
                logger.debug(
                    "supply_chain_lookup_skipped",
                    ticker=primary.ticker,
                    error=str(e),
                )
                dependencies = None

            enriched.append(
                {
                    **item,
                    "primary_ticker": primary.ticker,
                    "entities": entities,
                    "dependencies": dependencies,
                }
            )

        logger.info(
            "step_entity_resolution_complete",
            enriched_count=len(enriched),
            skipped_no_entities=skipped_no_entities,
        )
        return enriched

    async def _step_signal_generation(self, items: list[dict]) -> list[AlphaSignal]:
        """Step 3: Generate trading signals."""
        logger.info("step_signal_generation_start", item_count=len(items))

        signals = []
        decisions = {"BUY_LONG": 0, "WAIT": 0, "IGNORE": 0, "NO_GO": 0}

        for idx, item in enumerate(items):
            paper = item["paper"]
            ticker = item["primary_ticker"]

            logger.info(
                "processing_paper",
                progress=f"{idx + 1}/{len(items)}",
                paper_id=paper.id,
                ticker=ticker,
                title=paper.title[:60],
            )

            # Log full paper details for traceability (debug level)
            logger.debug(
                "paper_full_details",
                paper_id=paper.id,
                title=paper.title,
                abstract=paper.abstract,
                authors=getattr(paper, "authors", [])[:3],
                published=str(getattr(paper, "published", "")),
            )

            # Parallel analysis
            innovation_task = self.llm_agent.grade_innovation(
                text=paper.abstract,
                ticker=ticker,
                ticker_context=f"{ticker} context from graph",
                paper_id=paper.id,
            )

            # Fetch news for sentiment
            news = await self.news_fetcher.fetch_news([ticker])

            # Log news headlines used for sentiment (debug level)
            if news:
                logger.debug(
                    "news_for_sentiment",
                    ticker=ticker,
                    news_count=len(news),
                    headlines=[n.headline[:100] for n in news[:10]],
                )

            sentiment = await self.sentiment_engine.analyze_sentiment(news, ticker)

            innovation = await innovation_task

            # Log full innovation reasoning (debug level)
            logger.debug(
                "innovation_analysis_complete",
                paper_id=paper.id,
                ticker=ticker,
                score=innovation.score,
                full_reasoning=innovation.reasoning,
            )

            # Generate confluence signal
            signal = self.confluence_engine.generate_signal(
                ticker=ticker,
                innovation=innovation,
                sentiment=sentiment,
                source_type="arxiv",
            )

            # Log the decision with all input data
            logger.info(
                "signal_decision",
                paper_id=paper.id,
                ticker=ticker,
                action=signal.action.value,
                confidence=round(signal.confidence, 2),
                innovation_score=round(innovation.score, 2),
                sentiment_score=round(sentiment.score, 2),
                hype_volume=round(sentiment.hype_volume, 2),
                news_count=len(news),
                reasoning=signal.reasoning[:100] if signal.reasoning else "",
            )

            # Log full signal details (debug level)
            logger.debug(
                "signal_full_details",
                signal_id=signal.signal_id,
                paper_id=paper.id,
                ticker=ticker,
                action=signal.action.value,
                confidence=signal.confidence,
                full_reasoning=signal.reasoning,
                innovation_reasoning=innovation.reasoning,
                valid_until=str(signal.valid_until),
                risk_flags=[str(f) for f in signal.risk_flags],
            )

            decisions[signal.action.value] = decisions.get(signal.action.value, 0) + 1

            if signal.action not in (SignalAction.IGNORE, SignalAction.NO_GO):
                signals.append(signal)

        logger.info(
            "step_signal_generation_complete",
            signal_count=len(signals),
            decisions=decisions,
        )
        return signals

    async def _step_dispatch(self, signals: list[AlphaSignal]) -> list[AlphaSignal]:
        """Step 4: Validate liquidity and dispatch signals."""
        logger.info("step_dispatch_start", signal_count=len(signals))

        validated_signals = []
        for sig in signals:
            # Normalize ticker
            tradeable = self.ticker_normalizer.normalize(sig.ticker)
            sig.ticker = tradeable.symbol
            sig.venue = tradeable.venue
            sig.risk_flags.extend(tradeable.risk_flags)

            # Check liquidity
            market_state = await self.market_fetcher.fetch_market_state(sig.ticker)
            sig = self.liquidity_guard.validate_signal(sig, market_state)

            if sig.action != SignalAction.NO_GO:
                # Dispatch to Homeguard
                await self.dispatcher.dispatch(sig)

                # Record to journal
                await self.journal.record_signal(sig, market_state.price)

                validated_signals.append(sig)

        logger.info("step_dispatch_complete", dispatched_count=len(validated_signals))
        return validated_signals


async def run_single(orchestrator: VelitesOrchestrator) -> list[AlphaSignal]:
    """Run the pipeline once."""
    return await orchestrator.run_pipeline()


async def run_scheduled(orchestrator: VelitesOrchestrator) -> None:
    """Run the pipeline on a schedule using APScheduler."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error("apscheduler_not_installed", hint="pip install apscheduler")
        sys.exit(1)

    scheduler = AsyncIOScheduler()

    async def scheduled_run():
        """Wrapper for scheduled execution."""
        try:
            signals = await orchestrator.run_pipeline()
            logger.info("scheduled_run_complete", signals=len(signals))
        except Exception as e:
            logger.error("scheduled_run_failed", error=str(e))

    # Add job to run at specified interval
    scheduler.add_job(
        scheduled_run,
        trigger=IntervalTrigger(hours=settings.run_interval_hours),
        id="velites_pipeline",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "scheduler_started",
        interval_hours=settings.run_interval_hours,
        next_run=scheduler.get_job("velites_pipeline").next_run_time,
    )

    # Run immediately if configured
    if settings.run_at_startup:
        logger.info("running_at_startup")
        await scheduled_run()

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Keep running until shutdown
    try:
        await shutdown_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_shutdown")


async def main(mode: str | None = None) -> None:
    """
    Main entry point.

    Args:
        mode: Run mode - "single" or "scheduled" (default from settings)
    """
    configure_logging()
    run_mode = mode or settings.run_mode
    logger.info("velites_starting", version=settings.app_version, mode=run_mode)

    orchestrator = VelitesOrchestrator()
    await orchestrator.initialize()

    if run_mode == "scheduled":
        await run_scheduled(orchestrator)
    else:
        signals = await run_single(orchestrator)
        logger.info("velites_complete", signals=len(signals))


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Velites Quantamental Research Agent")
    parser.add_argument(
        "--mode",
        choices=["single", "scheduled"],
        default=None,
        help="Run mode: single (run once) or scheduled (run every N hours)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(mode=args.mode))
