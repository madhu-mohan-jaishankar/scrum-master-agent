"""Ingestion service entry point."""

import uvicorn
from ingestion.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "ingestion.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
