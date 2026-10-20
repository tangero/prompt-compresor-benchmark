# Headroom 0.41.0 jako lokální proxy v kontejneru agenta: Claude Code → headroom
# (localhost:8787) → gateway. Modely pro kompresi se stáhnou při buildu, za běhu offline.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
ARG VERSION=0.41.0
ENV HF_HOME=/home/node/.cache/huggingface HEADROOM_BEACON=off HEADROOM_UPDATE_CHECK=off HEADROOM_TELEMETRY=on
COPY --chown=node:node settings.json /home/node/.claude/settings.json
RUN python3 -m venv /home/node/tools/headroom \
 && /home/node/tools/headroom/bin/pip install -q --only-binary headroom-ai "headroom-ai[proxy]==${VERSION}" \
 && echo ${VERSION} > /home/node/tools/VERSION
ENV PATH=/home/node/tools/headroom/bin:$PATH
COPY --chown=node:node warmup.sh /home/node/tools/warmup.sh
RUN bash /home/node/tools/warmup.sh
ENV HF_HUB_OFFLINE=1 HEADROOM_OFFLINE=1
