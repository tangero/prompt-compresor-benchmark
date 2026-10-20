# Snapshot úlohy s nainstalovanými závislostmi. Kontext buildu = adresář snapshotu
# z scripts/make-snapshot.sh (bez historie, bez remote, bez skrytých testů).
ARG BASE=cc-bench-base
FROM ${BASE}
COPY --chown=node:node . /work
RUN pnpm install --frozen-lockfile && test -z "$(git status --porcelain --untracked-files=no)"
