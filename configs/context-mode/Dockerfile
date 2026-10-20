# Context Mode v1.0.169 jako plugin (MCP + hooky + skilly), lokální klon na tagu.
# Závislosti se doinstalují při buildu (npm 11; npm 10.9 z Node 22 padá na edgesOut),
# za běhu by je plugin stahoval z npm.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
ARG REF=v1.0.169
COPY --chown=node:node settings.json /home/node/.claude/settings.json
RUN git clone -q --depth 1 --branch ${REF} https://github.com/mksglu/context-mode /home/node/tools/context-mode \
 && claude plugin marketplace add /home/node/tools/context-mode </dev/null \
 && claude plugin install context-mode@context-mode </dev/null \
 && for d in $(find /home/node/.claude/plugins -name start.mjs -path '*context-mode*' -exec dirname {} \;) /home/node/tools/context-mode; do \
      (cd "$d" && npx -y npm@11.21.1 install --omit=dev --no-audit --no-fund >/dev/null); done \
 && git -C /home/node/tools/context-mode rev-parse HEAD > /home/node/tools/VERSION
