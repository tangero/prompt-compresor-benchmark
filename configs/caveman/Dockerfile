# Caveman v4.0.1 jako plugin z lokálního klonu na tagu (marketplace by vzal HEAD).
# SessionStart hook vloží SKILL.md; v headless režimu jen s CAVEMAN_DEFAULT_MODE.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
ARG REF=v4.0.1
ENV CAVEMAN_DEFAULT_MODE=caveman DO_NOT_TRACK=1
COPY --chown=node:node settings.json /home/node/.claude/settings.json
RUN git clone -q --depth 1 --branch ${REF} https://github.com/JuliusBrussee/caveman /home/node/tools/caveman \
 && claude plugin marketplace add /home/node/tools/caveman </dev/null \
 && claude plugin install caveman@caveman </dev/null \
 && touch /home/node/.claude/.caveman-nudge-shown \
 && git -C /home/node/tools/caveman rev-parse HEAD > /home/node/tools/VERSION
