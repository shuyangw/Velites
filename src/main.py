"""
Velites Main Orchestrator

The Event Loop that coordinates all modules in a DAG workflow.
Designed to run periodically (e.g., every 4 hours) via cron or scheduler.
"""

import asyncio
from datetime import datetime

from config import settings
from logging_config import configure_logging, get_logger
from modules.courier.models import AlphaSignal, SignalAction

# Module imports
from modules.scout import ArxivFetcher, NewsFetcher, MarketFetcher
from modules.mapper import GraphEngine, SupplyChainNavigator, TickerNormalizer
from modules.analyst import LLMAgent, SentimentEngine, ConfluenceEngine
from modules.courier import Dispatcher, LiquidityGuard
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
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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

            logger.info(
                "pipeline_run_complete",
                run_id=run_id,
                signals_generated=len(signals),
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
        for item in items:
            paper = item["paper"]
            text = f"{paper.title} {paper.abstract}"

            # Resolve entities
            entities = self.graph_engine.resolve_text(text)
            if not entities:
                continue

            # Get primary ticker
            primary = max(entities, key=lambda e: e.confidence)

            # Get supply chain dependencies
            dependencies = self.supply_chain.get_dependencies(primary.ticker)

            enriched.append({
                **item,
                "primary_ticker": primary.ticker,
                "entities": entities,
                "dependencies": dependencies,
            })

        logger.info("step_entity_resolution_complete", enriched_count=len(enriched))
        return enriched

    async def _step_signal_generation(self, items: list[dict]) -> list[AlphaSignal]:
        """Step 3: Generate trading signals."""
        logger.info("step_signal_generation_start", item_count=len(items))

        signals = []
        for item in items:
            paper = item["paper"]
            ticker = item["primary_ticker"]

            # Parallel analysis
            innovation_task = self.llm_agent.grade_innovation(
                text=paper.abstract,
                ticker=ticker,
                ticker_context=f"{ticker} context from graph",
                paper_id=paper.id,
            )

            # Fetch news for sentiment
            news = await self.news_fetcher.fetch_news([ticker])
            sentiment = await self.sentiment_engine.analyze_sentiment(news, ticker)

            innovation = await innovation_task

            # Generate confluence signal
            signal = self.confluence_engine.generate_signal(
                ticker=ticker,
                innovation=innovation,
                sentiment=sentiment,
                source_type="arxiv",
            )

            if signal.action not in (SignalAction.IGNORE, SignalAction.NO_GO):
                signals.append(signal)

        logger.info("step_signal_generation_complete", signal_count=len(signals))
        return signals

    async def _step_dispatch(self, signals: list[AlphaSignal]) -> list[AlphaSignal]:
        """Step 4: Validate liquidity and dispatch signals."""
        logger.info("step_dispatch_start", signal_count=len(signals))

        validated_signals = []
        for signal in signals:
            # Normalize ticker
            tradeable = self.ticker_normalizer.normalize(signal.ticker)
            signal.ticker = tradeable.symbol
            signal.venue = tradeable.venue
            signal.risk_flags.extend(tradeable.risk_flags)

            # Check liquidity
            market_state = await self.market_fetcher.fetch_market_state(signal.ticker)
            signal = self.liquidity_guard.validate_signal(signal, market_state)

            if signal.action != SignalAction.NO_GO:
                # Dispatch to Homeguard
                await self.dispatcher.dispatch(signal)

                # Record to journal
                await self.journal.record_signal(signal, market_state.price)

                validated_signals.append(signal)

        logger.info("step_dispatch_complete", dispatched_count=len(validated_signals))
        return validated_signals


async def main() -> None:
    """Main entry point."""
    configure_logging()
    logger.info("velites_starting", version=settings.app_version)

    orchestrator = VelitesOrchestrator()
    await orchestrator.initialize()
    signals = await orchestrator.run_pipeline()

    logger.info("velites_complete", signals=len(signals))


if __name__ == "__main__":
    asyncio.run(main())
