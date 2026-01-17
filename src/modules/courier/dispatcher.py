"""
The Payload Formatter - Homeguard Dispatcher

Creates standardized JSON contracts for the Homeguard execution system
and handles delivery via webhook or file output.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from config import settings
from logging_config import get_logger
from modules.courier.exceptions import DispatchError
from modules.courier.models import AlphaSignal

logger = get_logger(__name__)


class Dispatcher:
    """
    Formats and dispatches signals to Homeguard.

    Output format matches Homeguard's expected contract:
    {
        "source": "Velites_v1",
        "timestamp": "2026-01-16T12:00:00Z",
        "type": "QUANTAMENTAL_LONG",
        "ticker": "CAMT",
        "venue": "NASDAQ",
        "order_type": "LIMIT",
        "limit_price": 78.50,
        "validity": "24h",
        "reasoning": "...",
        "risk_flags": ["SMALL_CAP"]
    }
    """

    SOURCE_ID = "Velites_v1"

    def __init__(self) -> None:
        self.webhook_url = settings.homeguard_webhook_url
        self.output_dir = Path(settings.homeguard_output_dir)

    def format_payload(self, signal: AlphaSignal) -> dict[str, Any]:
        """
        Format an AlphaSignal into Homeguard payload.

        Args:
            signal: Signal to format

        Returns:
            Dict matching Homeguard contract
        """
        signal_type = f"QUANTAMENTAL_{signal.action.value}"

        return {
            "source": self.SOURCE_ID,
            "signal_id": signal.signal_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": signal_type,
            "ticker": signal.ticker,
            "venue": signal.venue,
            "order_type": signal.order_type.value,
            "limit_price": signal.limit_price,
            "validity": "24h",
            "confidence": signal.confidence,
            "reasoning": signal.reasoning,
            "risk_flags": [flag.value for flag in signal.risk_flags],
            "valid_until": signal.valid_until.isoformat() + "Z",
        }

    async def dispatch(self, signal: AlphaSignal) -> bool:
        """
        Dispatch signal to Homeguard.

        Args:
            signal: Signal to dispatch

        Returns:
            True if dispatch succeeded

        Raises:
            DispatchError: If dispatch fails
        """
        payload = self.format_payload(signal)

        logger.info(
            "dispatching_signal",
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            action=signal.action.value,
        )

        # Try webhook first, fall back to file
        if self.webhook_url:
            return await self._dispatch_webhook(payload)
        else:
            return await self._dispatch_file(payload)

    async def _dispatch_webhook(self, payload: dict[str, Any]) -> bool:
        """
        Dispatch signal via HTTP webhook POST to Homeguard.

        Args:
            payload: Formatted signal payload

        Returns:
            True if dispatch succeeded (2xx response)

        Raises:
            DispatchError: If webhook URL not configured or all retries fail
        """
        if not self.webhook_url:
            raise DispatchError("Webhook URL not configured")

        max_retries = 3
        backoff_seconds = [2, 4, 8]

        headers = {"Content-Type": "application/json"}

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers=headers,
                    )

                    if 200 <= response.status_code < 300:
                        logger.info(
                            "webhook_dispatch_success",
                            signal_id=payload.get("signal_id"),
                            status_code=response.status_code,
                        )
                        return True
                    else:
                        logger.warning(
                            "webhook_dispatch_failed",
                            signal_id=payload.get("signal_id"),
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        last_error = DispatchError(
                            f"Webhook returned {response.status_code}"
                        )

            except httpx.TimeoutException as e:
                logger.warning(
                    "webhook_timeout",
                    signal_id=payload.get("signal_id"),
                    attempt=attempt + 1,
                )
                last_error = e

            except httpx.RequestError as e:
                logger.warning(
                    "webhook_connection_error",
                    signal_id=payload.get("signal_id"),
                    attempt=attempt + 1,
                    error=str(e),
                )
                last_error = e

            # Wait before retry (except on last attempt)
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_seconds[attempt])

        # All retries exhausted
        raise DispatchError(f"Webhook dispatch failed after {max_retries} attempts: {last_error}")

    async def _dispatch_file(self, payload: dict[str, Any]) -> bool:
        """Dispatch by writing to file."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{payload['signal_id']}_{payload['ticker']}.json"
        filepath = self.output_dir / filename

        try:
            with open(filepath, "w") as f:
                json.dump(payload, f, indent=2)

            logger.info("signal_written_to_file", path=str(filepath))
            return True
        except Exception as e:
            raise DispatchError(f"Failed to write signal file: {e}")

    async def dispatch_batch(self, signals: list[AlphaSignal]) -> dict[str, bool]:
        """Dispatch multiple signals."""
        results = {}
        for signal in signals:
            try:
                results[signal.signal_id] = await self.dispatch(signal)
            except DispatchError as e:
                logger.error("batch_dispatch_failed", signal_id=signal.signal_id, error=str(e))
                results[signal.signal_id] = False
        return results
