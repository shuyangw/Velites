"""Tests for Journal class."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from modules.courier.models import AlphaSignal, SignalAction
from modules.scribe.db_models import SignalRecord
from modules.scribe.exceptions import JournalWriteError
from modules.scribe.journal import Journal


class TestJournalInitialization:
    """Tests for Journal initialization."""

    def test_init_default_url(self) -> None:
        """Test that Journal uses default database URL from settings."""
        journal = Journal()
        assert journal.database_url is not None
        assert "sqlite" in journal.database_url or "postgresql" in journal.database_url

    def test_init_custom_url(self) -> None:
        """Test that Journal accepts custom database URL."""
        custom_url = "sqlite:///custom_test.db"
        journal = Journal(database_url=custom_url)
        assert journal.database_url == custom_url

    def test_init_session_factory_none(self) -> None:
        """Test that session factory is None before initialization."""
        journal = Journal()
        assert journal._session_factory is None

    def test_initialize_creates_session_factory(self) -> None:
        """Test that initialize() creates session factory."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())
        assert journal._session_factory is not None

    def test_initialize_converts_sync_url(self) -> None:
        """Test that initialize() converts sync SQLite URL to async."""
        journal = Journal(database_url="sqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())
        # Should work without error - URL was converted internally
        assert journal._engine is not None

    def test_initialize_idempotent(self) -> None:
        """Test that multiple initialize() calls are safe."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())
        asyncio.get_event_loop().run_until_complete(journal.initialize())
        assert journal._session_factory is not None


class TestRecordSignal:
    """Tests for record_signal method."""

    @pytest.fixture
    def journal(self) -> Journal:
        """Create and initialize a test journal."""
        j = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(j.initialize())
        return j

    @pytest.fixture
    def sample_signal(self) -> AlphaSignal:
        """Create a sample signal for testing."""
        return AlphaSignal(
            signal_id="velites_test_001",
            action=SignalAction.BUY_LONG,
            ticker="NVDA",
            confidence=0.85,
            reasoning="Strong innovation score from ArXiv paper",
            valid_until=datetime.now(UTC) + timedelta(hours=24),
            source_paper_id="arxiv_2401.12345",
        )

    def test_record_signal_success(self, journal: Journal, sample_signal: AlphaSignal) -> None:
        """Test successful signal recording."""
        result = asyncio.get_event_loop().run_until_complete(
            journal.record_signal(sample_signal, 150.50)
        )
        assert result == sample_signal.signal_id

    def test_record_signal_returns_id(self, journal: Journal, sample_signal: AlphaSignal) -> None:
        """Test that record_signal returns the signal ID."""
        signal_id = asyncio.get_event_loop().run_until_complete(
            journal.record_signal(sample_signal, 100.0)
        )
        assert signal_id == "velites_test_001"

    def test_record_signal_persists_data(
        self, journal: Journal, sample_signal: AlphaSignal
    ) -> None:
        """Test that recorded signal can be retrieved."""
        asyncio.get_event_loop().run_until_complete(journal.record_signal(sample_signal, 150.50))

        signals = asyncio.get_event_loop().run_until_complete(journal.get_signals_for_backtest())

        assert len(signals) == 1
        assert signals[0]["id"] == sample_signal.signal_id
        assert signals[0]["ticker"] == "NVDA"
        assert signals[0]["market_price"] == 150.50

    def test_record_signal_all_fields(self, journal: Journal, sample_signal: AlphaSignal) -> None:
        """Test that all signal fields are stored correctly."""
        asyncio.get_event_loop().run_until_complete(journal.record_signal(sample_signal, 150.50))

        signals = asyncio.get_event_loop().run_until_complete(journal.get_signals_for_backtest())

        signal = signals[0]
        assert signal["ticker"] == "NVDA"
        assert signal["action"] == "BUY_LONG"
        assert signal["confidence"] == 0.85
        assert signal["reasoning"] == "Strong innovation score from ArXiv paper"
        assert signal["source_paper_id"] == "arxiv_2401.12345"
        assert signal["market_price"] == 150.50

    def test_record_signal_not_initialized(self, sample_signal: AlphaSignal) -> None:
        """Test that record_signal raises error if not initialized."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        # Don't call initialize()

        with pytest.raises(JournalWriteError, match="not initialized"):
            asyncio.get_event_loop().run_until_complete(journal.record_signal(sample_signal, 100.0))


class TestUpdateOutcome:
    """Tests for update_outcome method."""

    @pytest.fixture
    def journal_with_signal(self) -> tuple[Journal, str]:
        """Create journal with a recorded signal."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())

        signal = AlphaSignal(
            signal_id="velites_outcome_001",
            action=SignalAction.BUY,
            ticker="AMD",
            confidence=0.75,
            reasoning="Test signal for outcome",
            valid_until=datetime.now(UTC) + timedelta(hours=24),
        )

        asyncio.get_event_loop().run_until_complete(journal.record_signal(signal, 100.0))

        return journal, signal.signal_id

    def test_update_outcome_success(self, journal_with_signal: tuple[Journal, str]) -> None:
        """Test successful outcome update."""
        journal, signal_id = journal_with_signal
        outcome_date = datetime.now(UTC)

        asyncio.get_event_loop().run_until_complete(
            journal.update_outcome(signal_id, 110.0, outcome_date)
        )

        signals = asyncio.get_event_loop().run_until_complete(journal.get_signals_for_backtest())

        assert signals[0]["outcome_price"] == 110.0
        assert signals[0]["outcome_date"] is not None

    def test_update_outcome_overwrite(self, journal_with_signal: tuple[Journal, str]) -> None:
        """Test that outcome can be updated multiple times."""
        journal, signal_id = journal_with_signal
        outcome_date = datetime.now(UTC)

        # First update
        asyncio.get_event_loop().run_until_complete(
            journal.update_outcome(signal_id, 110.0, outcome_date)
        )

        # Second update (overwrite)
        asyncio.get_event_loop().run_until_complete(
            journal.update_outcome(signal_id, 120.0, outcome_date)
        )

        signals = asyncio.get_event_loop().run_until_complete(journal.get_signals_for_backtest())

        assert signals[0]["outcome_price"] == 120.0

    def test_update_outcome_nonexistent(self, journal_with_signal: tuple[Journal, str]) -> None:
        """Test that updating nonexistent signal raises error."""
        journal, _ = journal_with_signal

        with pytest.raises(JournalWriteError, match="not found"):
            asyncio.get_event_loop().run_until_complete(
                journal.update_outcome("nonexistent_id", 100.0, datetime.now(UTC))
            )

    def test_update_outcome_not_initialized(self) -> None:
        """Test that update_outcome raises error if not initialized."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")

        with pytest.raises(JournalWriteError, match="not initialized"):
            asyncio.get_event_loop().run_until_complete(
                journal.update_outcome("any_id", 100.0, datetime.now(UTC))
            )


class TestGetSignalsForBacktest:
    """Tests for get_signals_for_backtest method."""

    @pytest.fixture
    def journal_with_signals(self) -> Journal:
        """Create journal with multiple signals."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())

        # Create signals with different tickers and dates
        signals = [
            AlphaSignal(
                signal_id=f"velites_backtest_{i}",
                action=SignalAction.BUY,
                ticker=ticker,
                confidence=0.8,
                reasoning=f"Test signal {i}",
                valid_until=datetime.now(UTC) + timedelta(hours=24),
            )
            for i, ticker in enumerate(["NVDA", "AMD", "INTC", "NVDA"])
        ]

        for signal in signals:
            asyncio.get_event_loop().run_until_complete(journal.record_signal(signal, 100.0))

        return journal

    def test_get_signals_returns_all(self, journal_with_signals: Journal) -> None:
        """Test that get_signals returns all signals when no filter."""
        signals = asyncio.get_event_loop().run_until_complete(
            journal_with_signals.get_signals_for_backtest()
        )
        assert len(signals) == 4

    def test_get_signals_filter_by_ticker(self, journal_with_signals: Journal) -> None:
        """Test filtering by ticker."""
        signals = asyncio.get_event_loop().run_until_complete(
            journal_with_signals.get_signals_for_backtest(ticker="NVDA")
        )
        assert len(signals) == 2
        assert all(s["ticker"] == "NVDA" for s in signals)

    def test_get_signals_filter_by_date(self, journal_with_signals: Journal) -> None:
        """Test filtering by date range."""
        # All signals created now, so filter should include all
        start = datetime.now(UTC) - timedelta(hours=1)
        end = datetime.now(UTC) + timedelta(hours=1)

        signals = asyncio.get_event_loop().run_until_complete(
            journal_with_signals.get_signals_for_backtest(start_date=start, end_date=end)
        )
        assert len(signals) == 4

    def test_get_signals_empty_result(self, journal_with_signals: Journal) -> None:
        """Test that nonexistent ticker returns empty list."""
        signals = asyncio.get_event_loop().run_until_complete(
            journal_with_signals.get_signals_for_backtest(ticker="AAPL")
        )
        assert signals == []

    def test_get_signals_not_initialized(self) -> None:
        """Test that get_signals returns empty list if not initialized."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        signals = asyncio.get_event_loop().run_until_complete(journal.get_signals_for_backtest())
        assert signals == []


class TestGetSignalStats:
    """Tests for get_signal_stats method."""

    @pytest.fixture
    def journal_with_outcomes(self) -> Journal:
        """Create journal with signals that have outcomes."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())

        # Create signals with known outcomes
        test_data = [
            ("NVDA", 100.0, 120.0),  # 20% gain
            ("AMD", 100.0, 90.0),  # 10% loss
            ("INTC", 100.0, 110.0),  # 10% gain
            ("TSM", 100.0, 105.0),  # 5% gain
        ]

        for i, (ticker, market_price, outcome_price) in enumerate(test_data):
            signal = AlphaSignal(
                signal_id=f"velites_stats_{i}",
                action=SignalAction.BUY,
                ticker=ticker,
                confidence=0.8,
                reasoning="Test signal",
                valid_until=datetime.now(UTC) + timedelta(hours=24),
            )

            asyncio.get_event_loop().run_until_complete(journal.record_signal(signal, market_price))

            asyncio.get_event_loop().run_until_complete(
                journal.update_outcome(signal.signal_id, outcome_price, datetime.now(UTC))
            )

        return journal

    def test_get_stats_basic(self, journal_with_outcomes: Journal) -> None:
        """Test that stats returns expected structure."""
        stats = asyncio.get_event_loop().run_until_complete(
            journal_with_outcomes.get_signal_stats()
        )

        assert "total_signals" in stats
        assert "signals_with_outcome" in stats
        assert "win_rate" in stats
        assert "avg_return_pct" in stats
        assert "best_ticker" in stats
        assert "worst_ticker" in stats

    def test_get_stats_values(self, journal_with_outcomes: Journal) -> None:
        """Test that stats values are calculated correctly."""
        stats = asyncio.get_event_loop().run_until_complete(
            journal_with_outcomes.get_signal_stats()
        )

        assert stats["total_signals"] == 4
        assert stats["signals_with_outcome"] == 4
        # 3 wins (NVDA +20%, INTC +10%, TSM +5%), 1 loss (AMD -10%)
        assert stats["win_rate"] == 75.0
        # Average return: (20 - 10 + 10 + 5) / 4 = 6.25%
        assert stats["avg_return_pct"] == 6.25
        assert stats["best_ticker"] == "NVDA"
        assert stats["worst_ticker"] == "AMD"

    def test_get_stats_empty(self) -> None:
        """Test stats with no signals."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())

        stats = asyncio.get_event_loop().run_until_complete(journal.get_signal_stats())

        assert stats["total_signals"] == 0
        assert stats["signals_with_outcome"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["best_ticker"] is None

    def test_get_stats_no_outcomes(self) -> None:
        """Test stats with signals but no outcomes."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")
        asyncio.get_event_loop().run_until_complete(journal.initialize())

        signal = AlphaSignal(
            signal_id="velites_no_outcome",
            action=SignalAction.BUY,
            ticker="NVDA",
            confidence=0.8,
            reasoning="Test",
            valid_until=datetime.now(UTC) + timedelta(hours=24),
        )

        asyncio.get_event_loop().run_until_complete(journal.record_signal(signal, 100.0))

        stats = asyncio.get_event_loop().run_until_complete(journal.get_signal_stats())

        assert stats["total_signals"] == 1
        assert stats["signals_with_outcome"] == 0
        assert stats["win_rate"] == 0.0

    def test_get_stats_not_initialized(self) -> None:
        """Test that get_stats returns defaults if not initialized."""
        journal = Journal(database_url="sqlite+aiosqlite:///:memory:")

        stats = asyncio.get_event_loop().run_until_complete(journal.get_signal_stats())

        assert stats["total_signals"] == 0


class TestSignalRecordModel:
    """Tests for SignalRecord ORM model."""

    def test_to_dict(self) -> None:
        """Test SignalRecord.to_dict() method."""
        now = datetime.now(UTC)
        record = SignalRecord(
            id="test_id",
            ticker="NVDA",
            action="BUY",
            confidence=0.9,
            reasoning="Test reasoning",
            source_paper_id="arxiv_123",
            market_price=100.0,
            outcome_price=110.0,
            outcome_date=now,
            created_at=now,
        )

        d = record.to_dict()

        assert d["id"] == "test_id"
        assert d["ticker"] == "NVDA"
        assert d["action"] == "BUY"
        assert d["confidence"] == 0.9
        assert d["market_price"] == 100.0
        assert d["outcome_price"] == 110.0
