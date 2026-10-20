#!/usr/bin/env bash
# Vytvoří čistý snapshot úlohy: soubory výchozího commitu, git init, jeden commit,
# bez historie a bez remote. Záměrně ne git worktree (sdílí objekty s hlavním
# repozitářem, agent by si u úlohy 1 přečetl řešení přes `git show`).
#
# Použití: scripts/make-snapshot.sh <tasks/NN-name> <cílový adresář>
# Proměnná SOURCE_REPO: klon 3gpp-explorer (výchozí ~/GitHub/3gpp-explorer2).
set -euo pipefail

task_dir=$(cd "$1" && pwd)
dest=$2
src=${SOURCE_REPO:-$HOME/GitHub/3gpp-explorer2}
ref=$(tr -d '[:space:]' < "$task_dir/snapshot.ref")

if [ -e "$dest" ] && [ -n "$(ls -A "$dest" 2>/dev/null)" ]; then
  echo "cíl $dest není prázdný" >&2
  exit 1
fi
mkdir -p "$dest"

git -C "$src" cat-file -e "$ref^{commit}"
# Ne `git archive`: ten vynechá soubory s atributem export-ignore (.gitignore aj.).
tmp_index=$(mktemp)
rm -f "$tmp_index"
GIT_INDEX_FILE=$tmp_index git -C "$src" read-tree "$ref"
GIT_INDEX_FILE=$tmp_index git -C "$src" --work-tree="$(cd "$dest" && pwd)" checkout-index -a -f
rm -f "$tmp_index"

# Úpravy snapshotu společné pro všechny konfigurace (např. oprava CLAUDE.md).
if [ -x "$task_dir/snapshot-fixup.sh" ]; then
  (cd "$dest" && "$task_dir/snapshot-fixup.sh")
fi

cd "$dest"
git init -q -b main
git -c user.name=bench -c user.email=bench@localhost add -A
git -c user.name=bench -c user.email=bench@localhost commit -q -m "snapshot"
git -c user.name=bench -c user.email=bench@localhost tag base
echo "snapshot $(basename "$task_dir") @ ${ref:0:12} -> $dest"
