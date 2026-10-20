# Společný základ všech běhů: Node 22, pnpm 8.15.0, pevná verze Claude Code,
# neprivilegovaný uživatel (bypassPermissions pod rootem Claude Code odmítne).
FROM node:22-trixie-slim

ARG CLAUDE_CODE_VERSION=2.1.303
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl jq ripgrep procps python3 python3-venv coreutils \
 && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
 && corepack enable && corepack prepare pnpm@8.15.0 --activate

# node image už má uživatele node (uid 1000); přejmenovat nejde snadno, použijeme ho.
ENV HOME=/home/node \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
USER node
RUN corepack prepare pnpm@8.15.0 --activate && pnpm --version \
 && mkdir -p /home/node/.claude \
 && echo '{"hasCompletedOnboarding": true}' > /home/node/.claude.json \
 && git config --global user.name bench && git config --global user.email bench@localhost
WORKDIR /work
