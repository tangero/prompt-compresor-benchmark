#!/usr/bin/env bash
# Připraví CLAUDE.md pro konfigurace claude-md-lean/-full z obrazů úloh.
# Soubory obsahují interní údaje projektu, proto jsou v .gitignore.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
docker run --rm cc-bench-task-02 cat /work/CLAUDE.md > "$root/configs/claude-md-lean/CLAUDE.md"
docker run --rm cc-bench-task-01 cat /work/CLAUDE.md > "$root/configs/claude-md-full/CLAUDE.md"
wc -c "$root"/configs/claude-md-*/CLAUDE.md
