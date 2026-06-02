"""
Signal Viewer - Query and display journal database.

Usage:
    python scripts/view_signals.py --limit 20
    python scripts/view_signals.py --ticker NVDA --days 7
    python scripts/view_signals.py --signal-id velites_abc123
    python scripts/view_signals.py --export signals.csv
    python scripts/view_signals.py --stats --days 30
"""

import argparse
import asyncio
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import settings


def format_table(records: list[dict], columns: list[str]) -> str:
    """Format records as ASCII table."""
    if not records:
        return "No signals found."

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for record in records:
        for col in columns:
            val = str(record.get(col, ""))
            if len(val) > 60:
                val = val[:57] + "..."
            widths[col] = max(widths[col], len(val))

    # Build header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)

    # Build rows
    rows = []
    for record in records:
        row_vals = []
        for col in columns:
            val = str(record.get(col, ""))
            if len(val) > 60:
                val = val[:57] + "..."
            row_vals.append(val.ljust(widths[col]))
        rows.append(" | ".join(row_vals))

    return f"{header}\n{separator}\n" + "\n".join(rows)


def format_signal_detail(signal: dict) -> str:
    """Format a single signal with full details."""
    created_at = signal.get("created_at", "N/A")
    market_price = signal.get("market_price", 0)
    outcome_price = signal.get("outcome_price")

    outcome_str = "N/A"
    if outcome_price is not None and market_price > 0:
        change_pct = ((outcome_price - market_price) / market_price) * 100
        sign = "+" if change_pct >= 0 else ""
        outcome_str = f"${outcome_price:.2f} ({sign}{change_pct:.2f}%)"

    lines = [
        "=" * 70,
        f"Signal: {signal.get('id', 'N/A')}",
        "=" * 70,
        f"Created:      {created_at}",
        f"Ticker:       {signal.get('ticker', 'N/A')}",
        f"Action:       {signal.get('action', 'N/A')}",
        f"Confidence:   {signal.get('confidence', 0):.2f}",
        f"Entry Price:  ${market_price:.2f}",
        f"Outcome:      {outcome_str}",
        f"Source Paper: {signal.get('source_paper_id', 'N/A')}",
        "",
        "Reasoning:",
        "-" * 70,
        signal.get("reasoning", "No reasoning provided."),
        "-" * 70,
    ]
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    """Format statistics."""
    lines = [
        "=" * 50,
        "SIGNAL STATISTICS",
        "=" * 50,
        f"Total Signals:         {stats.get('total_signals', 0)}",
        f"With Outcome:          {stats.get('signals_with_outcome', 0)}",
        f"Win Rate:              {stats.get('win_rate', 0):.1f}%",
        f"Avg Return:            {stats.get('avg_return_pct', 0):.2f}%",
        f"Best Ticker:           {stats.get('best_ticker', 'N/A')}",
        f"Worst Ticker:          {stats.get('worst_ticker', 'N/A')}",
        "=" * 50,
    ]
    return "\n".join(lines)


async def main_async(args):
    """Async main function."""
    from modules.scribe import Journal

    journal = Journal(database_url=settings.database_url)
    await journal.initialize()

    # Show stats
    if args.stats:
        stats = await journal.get_signal_stats(days=args.days)
        print(format_stats(stats))
        return

    # Show single signal
    if args.signal_id:
        signal = await journal.get_signal_by_id(args.signal_id)
        if signal is None:
            print(f"Signal not found: {args.signal_id}")
            sys.exit(1)
        print(format_signal_detail(signal))
        return

    # Query signals
    start_date = None
    if args.days:
        start_date = datetime.now(timezone.utc) - timedelta(days=args.days)

    signals = await journal.get_signals_for_backtest(
        start_date=start_date,
        ticker=args.ticker,
    )

    # Apply limit
    if args.limit and len(signals) > args.limit:
        signals = signals[:args.limit]

    # Export to CSV
    if args.export:
        if not signals:
            print("No signals to export.")
            sys.exit(1)

        with open(args.export, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=signals[0].keys())
            writer.writeheader()
            writer.writerows(signals)
        print(f"Exported {len(signals)} signals to {args.export}")
        return

    # Display table
    columns = ["id", "created_at", "ticker", "action", "confidence", "market_price", "outcome_price"]

    # Format for display
    display_signals = []
    for s in signals:
        ds = s.copy()
        # Truncate ID
        if ds.get("id") and len(ds["id"]) > 20:
            ds["id"] = ds["id"][:17] + "..."
        # Format datetime
        if ds.get("created_at"):
            if isinstance(ds["created_at"], datetime):
                ds["created_at"] = ds["created_at"].strftime("%Y-%m-%d %H:%M")
            else:
                ds["created_at"] = str(ds["created_at"])[:16]
        # Format prices
        if ds.get("market_price"):
            ds["market_price"] = f"${ds['market_price']:.2f}"
        if ds.get("outcome_price"):
            ds["outcome_price"] = f"${ds['outcome_price']:.2f}"
        else:
            ds["outcome_price"] = "N/A"
        # Format confidence
        if ds.get("confidence") is not None:
            ds["confidence"] = f"{ds['confidence']:.2f}"
        display_signals.append(ds)

    print(format_table(display_signals, columns))
    print(f"\nTotal: {len(signals)} signals")


def main():
    parser = argparse.ArgumentParser(description="View Velites signals from journal")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of signals to show (default: 20)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Filter by ticker symbol",
    )
    parser.add_argument(
        "--signal-id",
        type=str,
        dest="signal_id",
        help="Show full details for a specific signal",
    )
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILE",
        help="Export signals to CSV file",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show aggregate statistics only",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
