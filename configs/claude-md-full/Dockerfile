# Baseline s plným CLAUDE.md (67 KB): verze před zkrácením
# (commit de97afa, snapshot úlohy 01). Použito pro úlohy 02/03, jejichž snapshot má 7 KB.
# CLAUDE.md připraví scripts/prepare-claude-md.sh (z obrazů úloh, mimo git).
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
COPY --chown=node:node settings.json /home/node/.claude/settings.json
COPY --chown=node:node CLAUDE.md /work/CLAUDE.md
RUN cd /work && git add CLAUDE.md && git commit -q --amend --no-edit && git tag -f base >/dev/null \
 && test -z "$(git status --porcelain --untracked-files=no)"
