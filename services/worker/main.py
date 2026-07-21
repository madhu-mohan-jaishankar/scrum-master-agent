"""Worker service entry point."""

import asyncio
import logging

from worker.consumer import consume

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.run(consume())
