#!/usr/bin/env python
"""Script to run the Velites pipeline manually or via scheduler."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from velites.main import main


if __name__ == "__main__":
    asyncio.run(main())
