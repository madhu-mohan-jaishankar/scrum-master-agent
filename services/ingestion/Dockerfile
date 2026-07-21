FROM registry.redhat.io/ubi9/python-311-minimal:latest

# Create non-root application user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Copy workspace packages needed by this service
COPY packages/shared packages/shared
COPY packages/context_store packages/context_store
COPY services/ingestion services/ingestion

# Install dependencies
RUN pip install --no-cache-dir \
    packages/shared \
    packages/context_store \
    services/ingestion

# Switch to non-root user
USER 1001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "ingestion.app:app", "--host", "127.0.0.1", "--port", "8000"]
