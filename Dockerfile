# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Base builder image intentionally includes only orchestration utilities.
# Stack-specific SDKs/toolchains should live in application runtime containers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    make \
    ripgrep \
    tini \
  && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 builder \
  && useradd --uid 10001 --gid builder --create-home --shell /bin/bash builder

WORKDIR /workspace

COPY --chown=builder:builder LICENSE BOUNDARY-POLICY.md CONTRIBUTING.md README.md CONSUMER-CONTRACT.md lifecycle-stage.yaml /workspace/
COPY --chown=builder:builder agents /workspace/agents
COPY --chown=builder:builder blueprint-setup /workspace/blueprint-setup
COPY --chown=builder:builder docker/agent-builder/entrypoint.sh /usr/local/bin/agent-builder

RUN pip install --no-cache-dir -r /workspace/agents/scripts/requirements.txt \
  && chmod +x /usr/local/bin/agent-builder

USER builder

ENTRYPOINT ["/usr/bin/tini", "--", "agent-builder"]
CMD ["bash"]
