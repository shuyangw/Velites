"""
The Journal - Persistent Signal Record

Maintains a database of all signals for backtesting and analysis.
Schema: (Date, SignalID, Ticker, Input_Paper, LLM_Reasoning, Market_Price_At_Signal, Outcome_7d)
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from logging_config import get_logger
from modules.courier.models import AlphaSignal
from modules.scribe.db_models import Base, SignalRecord
from modules.scribe.exceptions import JournalWriteError

logger = get_logger(__name__)


class Journal:
    """
    Persistent journal for signal tracking and backtesting.

    Supports SQLite (local development) or PostgreSQL (production).
    """

    def __init__(self, database_url: str | None = None) -> None:
        """
        Initialize the journal.

        Args:
            database_url: Database connection URL (default from settings)
        """
        self.database_url = database_url or settings.database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        """
        Initialize database connection and create tables.

        Creates async engine and session factory, then ensures tables exist.
        """
        logger.info("initializing_journal", database_url=self.database_url)

        # Convert sync URL to async URL if needed
        db_url = self.database_url
        if db_url.startswith("sqlite:///") and "+aiosqlite" not in db_url:
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        # Create async engine
        self._engine = create_async_engine(db_url, echo=False)

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("journal_initialized")

    async def record_signal(self, signal: AlphaSignal, market_price: float) -> str:
        """
        Record a signal to the journal.

        Args:
            signal: Signal to record
            market_price: Market price at time of signal

        Returns:
            Record ID (signal_id)

        Raises:
            JournalWriteError: If write fails
        """
        if self._session_factory is None:
            raise JournalWriteError("Journal not initialized - call initialize() first")

        logger.info(
            "recording_signal",
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            market_price=market_price,
        )

        try:
            async with self._session_factory() as session:
                record = SignalRecord(
                    id=signal.signal_id,
                    ticker=signal.ticker,
                    action=signal.action.value,
                    confidence=signal.confidence,
                    reasoning=signal.reasoning,
                    source_paper_id=signal.source_paper_id,
                    market_price=market_price,
                    created_at=datetime.now(UTC),
                )

                session.add(record)
                await session.commit()

                logger.info("signal_recorded", signal_id=signal.signal_id)
                return signal.signal_id

        except Exception as e:
            logger.error("signal_record_failed", signal_id=signal.signal_id, error=str(e))
            raise JournalWriteError(f"Failed to record signal: {e}")

    async def update_outcome(
        self, signal_id: str, outcome_price: float, outcome_date: datetime
    ) -> None:
        """
        Update a signal record with its outcome.

        Args:
            signal_id: ID of signal to update
            outcome_price: Price at outcome date
            outcome_date: Date of outcome measurement

        Raises:
            JournalWriteError: If update fails or signal not found
        """
        if self._session_factory is None:
            raise JournalWriteError("Journal not initialized - call initialize() first")

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(SignalRecord).where(SignalRecord.id == signal_id)
                )
                record = result.scalar_one_or_none()

                if record is None:
                    raise JournalWriteError(f"Signal not found: {signal_id}")

                record.outcome_price = outcome_price  # type: ignore[assignment]  # SQLAlchemy Column vs Python type
                record.outcome_date = outcome_date  # type: ignore[assignment]  # SQLAlchemy Column vs Python type

                await session.commit()

                logger.info(
                    "outcome_updated",
                    signal_id=signal_id,
                    outcome_price=outcome_price,
                )

        except JournalWriteError:
            raise
        except Exception as e:
            logger.error("outcome_update_failed", signal_id=signal_id, error=str(e))
            raise JournalWriteError(f"Failed to update outcome: {e}")

    async def get_signals_for_backtest(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        ticker: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve signals for backtesting analysis.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            ticker: Filter by ticker

        Returns:
            List of signal records with outcomes as dicts
        """
        if self._session_factory is None:
            return []

        try:
            async with self._session_factory() as session:
                query = select(SignalRecord)

                # Apply filters
                if start_date is not None:
                    query = query.where(SignalRecord.created_at >= start_date)
                if end_date is not None:
                    query = query.where(SignalRecord.created_at <= end_date)
                if ticker is not None:
                    query = query.where(SignalRecord.ticker == ticker)

                # Order by created_at descending
                query = query.order_by(SignalRecord.created_at.desc())

                result = await session.execute(query)
                records = result.scalars().all()

                return [record.to_dict() for record in records]

        except Exception as e:
            logger.error("backtest_query_failed", error=str(e))
            return []

    async def get_signal_stats(self, days: int = 30) -> dict[str, Any]:
        """
        Get aggregate statistics for recent signals.

        Args:
            days: Number of days to look back

        Returns:
            Dict with statistics:
            - total_signals: Total number of signals
            - signals_with_outcome: Signals that have outcome data
            - win_rate: Percentage of winning trades
            - avg_return_pct: Average return percentage
            - best_ticker: Best performing ticker
            - worst_ticker: Worst performing ticker
        """
        if self._session_factory is None:
            return {
                "total_signals": 0,
                "signals_with_outcome": 0,
                "win_rate": 0.0,
                "avg_return_pct": 0.0,
                "best_ticker": None,
                "worst_ticker": None,
            }

        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            async with self._session_factory() as session:
                # Get all signals in date range
                query = select(SignalRecord).where(SignalRecord.created_at >= cutoff_date)
                result = await session.execute(query)
                records = result.scalars().all()

                total_signals = len(records)
                if total_signals == 0:
                    return {
                        "total_signals": 0,
                        "signals_with_outcome": 0,
                        "win_rate": 0.0,
                        "avg_return_pct": 0.0,
                        "best_ticker": None,
                        "worst_ticker": None,
                    }

                # Filter to signals with outcomes
                with_outcome = [
                    r for r in records if r.outcome_price is not None and r.market_price > 0
                ]
                signals_with_outcome = len(with_outcome)

                if signals_with_outcome == 0:
                    return {
                        "total_signals": total_signals,
                        "signals_with_outcome": 0,
                        "win_rate": 0.0,
                        "avg_return_pct": 0.0,
                        "best_ticker": None,
                        "worst_ticker": None,
                    }

                # Calculate returns
                returns = []
                ticker_returns: dict[str, list[float]] = {}

                for r in with_outcome:
                    # For BUY signals, positive return = outcome > market
                    # For other signals, we still measure price movement
                    return_pct = ((r.outcome_price - r.market_price) / r.market_price) * 100
                    returns.append(return_pct)

                    if r.ticker not in ticker_returns:
                        ticker_returns[r.ticker] = []  # type: ignore[index]  # SQLAlchemy Column[str] as index
                    ticker_returns[r.ticker].append(return_pct)  # type: ignore[index, arg-type]  # SQLAlchemy Column[str] as index; ColumnElement[float] vs float

                # Win rate (positive returns for BUY signals)
                wins = sum(1 for r in returns if r > 0)
                win_rate = (wins / len(returns)) * 100 if returns else 0.0

                # Average return
                avg_return_pct = sum(returns) / len(returns) if returns else 0.0

                # Best/worst tickers by average return
                ticker_avg = {t: sum(rets) / len(rets) for t, rets in ticker_returns.items()}

                best_ticker = max(ticker_avg, key=ticker_avg.get) if ticker_avg else None  # type: ignore[arg-type]  # dict.get overload
                worst_ticker = min(ticker_avg, key=ticker_avg.get) if ticker_avg else None  # type: ignore[arg-type]  # dict.get overload

                return {
                    "total_signals": total_signals,
                    "signals_with_outcome": signals_with_outcome,
                    "win_rate": round(win_rate, 2),
                    "avg_return_pct": round(avg_return_pct, 2),
                    "best_ticker": best_ticker,
                    "worst_ticker": worst_ticker,
                }

        except Exception as e:
            logger.error("stats_query_failed", error=str(e))
            return {
                "total_signals": 0,
                "signals_with_outcome": 0,
                "win_rate": 0.0,
                "avg_return_pct": 0.0,
                "best_ticker": None,
                "worst_ticker": None,
            }

    async def get_signal_by_id(self, signal_id: str) -> dict[str, Any] | None:
        """
        Retrieve a single signal by ID.

        Args:
            signal_id: The signal ID to look up

        Returns:
            Signal record as dict, or None if not found
        """
        if self._session_factory is None:
            return None

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(SignalRecord).where(SignalRecord.id == signal_id)
                )
                record = result.scalar_one_or_none()

                if record is None:
                    return None

                return record.to_dict()

        except Exception as e:
            logger.error("signal_query_failed", signal_id=signal_id, error=str(e))
            return None
