FROM registry.redhat.io/ubi9/python-311-minimal:latest

RUN useradd -m -u 1001 appuser

WORKDIR /app

COPY packages/shared packages/shared
COPY services/scheduler services/scheduler

RUN pip install --no-cache-dir \
    packages/shared \
    services/scheduler

USER 1001

CMD ["python", "services/scheduler/main.py"]
