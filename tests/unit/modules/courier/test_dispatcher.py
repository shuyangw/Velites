"""Tests for Dispatcher."""

import asyncio
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.courier.dispatcher import Dispatcher
from modules.courier.exceptions import DispatchError
from modules.courier.models import AlphaSignal, OrderType, SignalAction
from modules.mapper.models import RiskFlag


class TestFormatPayload:
    """Tests for format_payload method."""

    @pytest.fixture
    def sample_signal(self) -> AlphaSignal:
        """Create a sample AlphaSignal for testing."""
        return AlphaSignal(
            signal_id="velites_test123",
            action=SignalAction.BUY_LONG,
            ticker="ASML",
            venue="NASDAQ",
            order_type=OrderType.LIMIT,
            limit_price=750.50,
            confidence=0.85,
            reasoning="ArXiv paper suggests moat expansion",
            valid_until=datetime(2026, 1, 17, 10, 0, 0, tzinfo=UTC),
            risk_flags=[RiskFlag.SMALL_CAP],
        )

    def test_format_payload_structure(self, sample_signal: AlphaSignal) -> None:
        """Test that payload contains all required Homeguard fields."""
        dispatcher = Dispatcher()
        payload = dispatcher.format_payload(sample_signal)

        # Verify all required fields exist
        assert "source" in payload
        assert "signal_id" in payload
        assert "timestamp" in payload
        assert "type" in payload
        assert "ticker" in payload
        assert "venue" in payload
        assert "order_type" in payload
        assert "limit_price" in payload
        assert "validity" in payload
        assert "confidence" in payload
        assert "reasoning" in payload
        assert "risk_flags" in payload
        assert "valid_until" in payload

    def test_format_payload_values(self, sample_signal: AlphaSignal) -> None:
        """Test that payload values match signal."""
        dispatcher = Dispatcher()
        payload = dispatcher.format_payload(sample_signal)

        assert payload["source"] == "Velites_v1"
        assert payload["signal_id"] == "velites_test123"
        assert payload["ticker"] == "ASML"
        assert payload["venue"] == "NASDAQ"
        assert payload["order_type"] == "LIMIT"
        assert payload["limit_price"] == 750.50
        assert payload["confidence"] == 0.85
        assert payload["validity"] == "24h"

    def test_format_payload_signal_type_format(self, sample_signal: AlphaSignal) -> None:
        """Test that type is formatted as QUANTAMENTAL_{action}."""
        dispatcher = Dispatcher()
        payload = dispatcher.format_payload(sample_signal)

        assert payload["type"] == "QUANTAMENTAL_BUY_LONG"

    def test_format_payload_risk_flags_serialized(self, sample_signal: AlphaSignal) -> None:
        """Test that risk flags are serialized to string values."""
        dispatcher = Dispatcher()
        payload = dispatcher.format_payload(sample_signal)

        assert payload["risk_flags"] == ["SMALL_CAP"]

    def test_format_payload_timestamp_iso_format(self, sample_signal: AlphaSignal) -> None:
        """Test that timestamps are in ISO format with UTC offset."""
        dispatcher = Dispatcher()
        payload = dispatcher.format_payload(sample_signal)

        assert "+00:00" in payload["timestamp"]
        assert "+00:00" in payload["valid_until"]


class TestDispatchFile:
    """Tests for file dispatch."""

    @pytest.fixture
    def sample_signal(self) -> AlphaSignal:
        """Create a sample AlphaSignal for testing."""
        return AlphaSignal(
            signal_id="velites_file_test",
            action=SignalAction.BUY,
            ticker="NVDA",
            confidence=0.9,
            reasoning="Test signal",
            valid_until=datetime.now(UTC) + timedelta(hours=24),
        )

    def test_dispatch_file_creates_json(self, sample_signal: AlphaSignal) -> None:
        """Test that file dispatch creates valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = Dispatcher()
            dispatcher.output_dir = Path(tmpdir)
            dispatcher.webhook_url = ""  # Force file dispatch

            payload = dispatcher.format_payload(sample_signal)
            result = asyncio.get_event_loop().run_until_complete(dispatcher._dispatch_file(payload))

            assert result is True

            # Verify file exists and contains valid JSON
            expected_file = Path(tmpdir) / f"{sample_signal.signal_id}_{sample_signal.ticker}.json"
            assert expected_file.exists()

            with open(expected_file) as f:
                saved_payload = json.load(f)

            assert saved_payload["signal_id"] == sample_signal.signal_id
            assert saved_payload["ticker"] == sample_signal.ticker

    def test_dispatch_file_creates_directory(self, sample_signal: AlphaSignal) -> None:
        """Test that file dispatch creates output directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "output"

            dispatcher = Dispatcher()
            dispatcher.output_dir = nested_dir
            dispatcher.webhook_url = ""

            payload = dispatcher.format_payload(sample_signal)
            result = asyncio.get_event_loop().run_until_complete(dispatcher._dispatch_file(payload))

            assert result is True
            assert nested_dir.exists()


class TestDispatchWebhook:
    """Tests for webhook dispatch."""

    @pytest.fixture
    def sample_payload(self) -> dict:
        """Create a sample payload for testing."""
        return {
            "source": "Velites_v1",
            "signal_id": "velites_webhook_test",
            "timestamp": "2026-01-17T12:00:00Z",
            "type": "QUANTAMENTAL_BUY_LONG",
            "ticker": "AMD",
            "venue": "NASDAQ",
            "order_type": "LIMIT",
            "limit_price": 150.00,
            "validity": "24h",
            "confidence": 0.8,
            "reasoning": "Test signal",
            "risk_flags": [],
            "valid_until": "2026-01-18T12:00:00Z",
        }

    def test_dispatch_webhook_missing_url(self, sample_payload: dict) -> None:
        """Test that missing webhook URL raises DispatchError."""
        dispatcher = Dispatcher()
        dispatcher.webhook_url = ""

        with pytest.raises(DispatchError, match="not configured"):
            asyncio.get_event_loop().run_until_complete(
                dispatcher._dispatch_webhook(sample_payload)
            )

    def test_dispatch_webhook_success(self, sample_payload: dict) -> None:
        """Test successful webhook POST."""
        dispatcher = Dispatcher()
        dispatcher.webhook_url = "https://example.com/webhook"

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("modules.courier.dispatcher.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = asyncio.get_event_loop().run_until_complete(
                dispatcher._dispatch_webhook(sample_payload)
            )

            assert result is True
            mock_client.post.assert_called_once()

    def test_dispatch_webhook_retry_on_error(self, sample_payload: dict) -> None:
        """Test that webhook retries on connection error."""
        import httpx

        dispatcher = Dispatcher()
        dispatcher.webhook_url = "https://example.com/webhook"

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        with patch("modules.courier.dispatcher.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Patch asyncio.sleep to speed up test
            with patch("modules.courier.dispatcher.asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.get_event_loop().run_until_complete(
                    dispatcher._dispatch_webhook(sample_payload)
                )

            assert result is True
            assert call_count == 3  # Failed twice, succeeded on third

    def test_dispatch_webhook_all_retries_fail(self, sample_payload: dict) -> None:
        """Test that DispatchError is raised after all retries fail."""
        import httpx

        dispatcher = Dispatcher()
        dispatcher.webhook_url = "https://example.com/webhook"

        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        with patch("modules.courier.dispatcher.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Patch asyncio.sleep to speed up test
            with patch("modules.courier.dispatcher.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(DispatchError, match="failed after 3 attempts"):
                    asyncio.get_event_loop().run_until_complete(
                        dispatcher._dispatch_webhook(sample_payload)
                    )

    def test_dispatch_webhook_non_2xx_response(self, sample_payload: dict) -> None:
        """Test that non-2xx responses are retried."""
        dispatcher = Dispatcher()
        dispatcher.webhook_url = "https://example.com/webhook"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("modules.courier.dispatcher.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Patch asyncio.sleep to speed up test
            with patch("modules.courier.dispatcher.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(DispatchError, match="failed after 3 attempts"):
                    asyncio.get_event_loop().run_until_complete(
                        dispatcher._dispatch_webhook(sample_payload)
                    )


class TestDispatch:
    """Tests for main dispatch method."""

    @pytest.fixture
    def sample_signal(self) -> AlphaSignal:
        """Create a sample AlphaSignal for testing."""
        return AlphaSignal(
            signal_id="velites_dispatch_test",
            action=SignalAction.BUY_LONG,
            ticker="TSM",
            confidence=0.75,
            reasoning="Test dispatch",
            valid_until=datetime.now(UTC) + timedelta(hours=24),
        )

    def test_dispatch_uses_webhook_when_configured(self, sample_signal: AlphaSignal) -> None:
        """Test that dispatch uses webhook when URL is configured."""
        dispatcher = Dispatcher()
        dispatcher.webhook_url = "https://example.com/webhook"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("modules.courier.dispatcher.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = asyncio.get_event_loop().run_until_complete(dispatcher.dispatch(sample_signal))

            assert result is True
            mock_client.post.assert_called_once()

    def test_dispatch_falls_back_to_file(self, sample_signal: AlphaSignal) -> None:
        """Test that dispatch falls back to file when webhook not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = Dispatcher()
            dispatcher.webhook_url = ""
            dispatcher.output_dir = Path(tmpdir)

            result = asyncio.get_event_loop().run_until_complete(dispatcher.dispatch(sample_signal))

            assert result is True

            # Verify file was created
            expected_file = Path(tmpdir) / f"{sample_signal.signal_id}_{sample_signal.ticker}.json"
            assert expected_file.exists()


class TestDispatchBatch:
    """Tests for batch dispatch."""

    def test_dispatch_batch_handles_failures(self) -> None:
        """Test that batch dispatch tracks partial failures."""
        signals = [
            AlphaSignal(
                signal_id=f"velites_batch_{i}",
                action=SignalAction.BUY,
                ticker=ticker,
                confidence=0.8,
                reasoning="Batch test",
                valid_until=datetime.now(UTC) + timedelta(hours=24),
            )
            for i, ticker in enumerate(["AAPL", "GOOGL", "MSFT"])
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = Dispatcher()
            dispatcher.webhook_url = ""
            dispatcher.output_dir = Path(tmpdir)

            results = asyncio.get_event_loop().run_until_complete(
                dispatcher.dispatch_batch(signals)
            )

            # All should succeed with file dispatch
            assert all(results.values())
            assert len(results) == 3

    def test_dispatch_batch_empty_list(self) -> None:
        """Test batch dispatch with empty list."""
        dispatcher = Dispatcher()

        results = asyncio.get_event_loop().run_until_complete(dispatcher.dispatch_batch([]))

        assert results == {}
