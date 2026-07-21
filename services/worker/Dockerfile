FROM registry.redhat.io/ubi9/python-311-minimal:latest

RUN useradd -m -u 1001 appuser

WORKDIR /app

COPY packages/shared packages/shared
COPY packages/watsonx_client packages/watsonx_client
COPY packages/processors packages/processors
COPY packages/context_store packages/context_store
COPY packages/dispatcher packages/dispatcher
COPY services/worker services/worker

# Install all workspace deps — redis replaces aiokafka/sqlalchemy
RUN pip install --no-cache-dir \
    packages/shared \
    packages/watsonx_client \
    packages/processors \
    packages/context_store \
    packages/dispatcher \
    services/worker

USER 1001

CMD ["python", "services/worker/main.py"]
