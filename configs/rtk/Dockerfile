# RTK v1.0.1, prebuilt binárka; `rtk init -g --auto-patch` zapíše PreToolUse hook
# do ~/.claude/settings.json (bez --auto-patch se bez TTY nezapíše nic).
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
ARG REF=v1.0.1
ENV RTK_TELEMETRY_DISABLED=1
COPY --chown=node:node settings.json /home/node/.claude/settings.json
RUN mkdir -p /home/node/.local/bin /home/node/tools \
 && case "$(uname -m)" in aarch64) a=aarch64-unknown-linux-gnu ;; x86_64) a=x86_64-unknown-linux-musl ;; esac \
 && curl -fsSL "https://github.com/rtk-ai/rtk/releases/download/${REF}/rtk-${a}.tar.gz" | tar -xz -C /home/node/.local/bin rtk \
 && /home/node/.local/bin/rtk --version > /home/node/tools/VERSION
ENV PATH=/home/node/.local/bin:$PATH
RUN rtk init -g --auto-patch </dev/null && grep -q 'rtk hook' /home/node/.claude/settings.json
