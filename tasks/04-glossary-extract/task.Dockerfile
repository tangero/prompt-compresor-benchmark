# Obraz úlohy 04 = docker/task/Dockerfile + unzip. Sada spec-pipeline obsahuje test
# validateDocx, který volá unzip; bez něj by agent viděl selhání nesouvisející s úlohou
# (u úlohy 02 se to stalo, viz REPORT.md).
ARG BASE=cc-bench-base
FROM ${BASE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/*
USER node
COPY --chown=node:node . /work
RUN pnpm install --frozen-lockfile && test -z "$(git status --porcelain --untracked-files=no)"
