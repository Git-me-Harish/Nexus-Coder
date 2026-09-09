# Execution image for agent-generated code.
#
#   docker build -t nexus-sandbox:latest backend/sandbox/
#
# Deliberately boring: a pinned Python base plus Node, a few universally
# useful CLI tools, and the common test runners. It carries NO credentials
# and NO network access at runtime (see app/agents/sandbox.py, which starts
# containers with network_mode="none"), so anything needed at run time must
# already be baked in here.
#
# Keep this lean. Every package added is more attack surface running
# model-authored code, and a slower cold start on the user's first command.
FROM python:3.12-slim-bookworm

# Node for JS/TS projects; git for repo-shaped tasks; ripgrep+jq because
# agents reach for them constantly and shelling out to them beats writing
# throwaway search scripts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm git ca-certificates ripgrep jq curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        pytest pytest-asyncio requests httpx pydantic rich

# Matches the user= the runner starts containers with. Running as root inside
# the container would also leave root-owned files in the bind-mounted
# workspace, which the API process then could not clean up.
RUN useradd --uid 1000 --create-home --shell /bin/bash agent

WORKDIR /workspace
USER 1000:1000

CMD ["/bin/sh"]
