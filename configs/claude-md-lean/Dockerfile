# Baseline se štíhlým CLAUDE.md (7 KB): verze, na kterou projekt CLAUDE.md sám zkrátil
# (commit 750d8fb, snapshot úloh 02/03). Použito pro úlohu 01, jejíž snapshot má 67 KB.
# CLAUDE.md připraví scripts/prepare-claude-md.sh (z obrazů úloh, mimo git).
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
COPY --chown=node:node settings.json /home/node/.claude/settings.json
COPY --chown=node:node CLAUDE.md /work/CLAUDE.md
RUN cd /work && git add CLAUDE.md && git commit -q --amend --no-edit && git tag -f base >/dev/null \
 && test -z "$(git status --porcelain --untracked-files=no)"
