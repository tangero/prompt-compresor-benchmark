# Ponytail v5.3.2 jako plugin z lokálního klonu na tagu. Aktivuje se SessionStart
# hookem (výchozí úroveň full). statusLine v settings.json jen potlačí jednorázovou
# výzvu k nastavení, v -p se nezobrazuje.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
ARG REF=v5.3.2
COPY --chown=node:node settings.json /home/node/.claude/settings.json
RUN git clone -q --depth 1 --branch ${REF} https://github.com/DietrichGebert/ponytail /home/node/tools/ponytail \
 && claude plugin marketplace add /home/node/tools/ponytail </dev/null \
 && claude plugin install ponytail@ponytail </dev/null \
 && git -C /home/node/tools/ponytail rev-parse HEAD > /home/node/tools/VERSION
