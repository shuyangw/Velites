#!/usr/bin/env python
"""Script to run the Velites pipeline manually or via scheduler."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import main


def parse_args():
    parser = argparse.ArgumentParser(description="Run Velites pipeline")
    parser.add_argument(
        "--mode",
        choices=["single", "scheduled"],
        default="single",
        help="Run mode: single (run once) or scheduled (run every N hours)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(mode=args.mode))
